from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langfuse.langchain import CallbackHandler
from typing import List, Optional, Dict, Any, Callable
from pydantic import BaseModel
import json
import os
import asyncio
import sys
import io

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tool_utils import tool_executor_sync

class AgentState(BaseModel):
    messages: List[Dict[str, str]] = []
    last_response: Optional[Dict[str, Any]] = None

class AgrifactAgent:
    def __init__(self, llm: BaseChatModel, tool_descriptions: List[Dict], tool_executor: Callable):
        self.llm = llm
        self.tool_descriptions = [tool_desc for tool_desc in tool_descriptions if tool_desc["name"] in ["weather", "market", "disease", "soil", "policy", "insurance", "climate", "disaster", "agri_fact_search"]]
        self.tool_executor = tool_executor
        self.system_prompt = self._build_system_prompt()
        # self.langfuse_handler = CallbackHandler()
        self.app = self.build_workflow()
    
    def _build_system_prompt(self) -> str:
        tools_info = "\n".join([
            f"Tool: {tool['name']}\nDescription: {tool['description']}\nParameters: {tool['inputSchema']}"
            for tool in self.tool_descriptions
        ])
        
        return f"""You are a specialized agricultural assistant helping farmers with crop-related information, weather data, soil analysis, and disease diagnosis.

AVAILABLE TOOLS:
{tools_info}

CRITICAL OUTPUT RULES:
- You MUST respond with ONLY valid JSON
- NO markdown formatting, NO code blocks, NO extra text
- Return ONLY the JSON object, nothing else

OUTPUT FORMATS:

For tool calls (when you need external data):
{{"type": "tool_calls", "tool_calls": [{{"name": "tool_name", "arguments": {{"param": "value"}}}}]}}

For final responses (when you have sufficient information):
{{"type": "final_response", "response": "Your detailed agricultural answer with analysis and recommendations"}}

WORKFLOW:
1. Analyze the user's agricultural query
2. If you need external data (weather, soil, disease info, etc.) → make tool calls
3. If you can answer directly → provide final response
4. After receiving tool results → ALWAYS provide a comprehensive final response

AGRICULTURAL EXPERTISE:
- Weather forecasts and climate data
- Soil composition and nutrient analysis
- Plant disease identification and treatment
- Crop management recommendations
- Government agricultural policies
- Disaster alerts and warnings
- Market information for crops

EXAMPLES:

Weather Query:
{{"type": "tool_calls", "tool_calls": [{{"name": "weather", "arguments": {{"lat": 28.7041, "lon": 77.1025}}}}]}}

Disease Analysis:
{{"type": "tool_calls", "tool_calls": [{{"name": "disease", "arguments": {{"image_url": "https://example.com/plant.jpg"}}}}]}}

Soil Analysis:
{{"type": "tool_calls", "tool_calls": [{{"name": "soil", "arguments": {{"lat": 28.7041, "lon": 77.1025}}}}]}}

Direct Response:
{{"type": "final_response", "response": "Crop rotation involves systematically changing the types of crops grown in a field to improve soil health and reduce pest buildup."}}

Remember: Return ONLY valid JSON, no additional text."""

    def build_workflow(self):
        def debug_node(node_name):
            def wrapper(func):
                def inner(*args, **kwargs):
                    print(f"🔄 ENTERING NODE: {node_name}")
                    print(f"   Input: {args[0] if args else 'No args'}")
                    result = func(*args, **kwargs)
                    print(f"✅ EXITING NODE: {node_name}")
                    print(f"   Output keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                    return result
                return inner
            return wrapper
        
        workflow = StateGraph(AgentState)
        workflow.add_node("call_agent", debug_node("call_agent")(self._call_agent))
        workflow.add_node("execute_tools", debug_node("execute_tools")(self._execute_tools))
        workflow.set_entry_point("call_agent")
        workflow.add_conditional_edges(
            "call_agent",
            self._should_execute_tools,
            {"execute_tools": "execute_tools", "end": END}
        )
        workflow.add_edge("execute_tools", "call_agent")
        # return workflow.compile().with_config(config={"callbacks": [self.langfuse_handler]})
        return workflow.compile()
    
    def _call_agent(self, state: AgentState) -> Dict[str, Any]:
        llm_messages = state.messages
        
        print(f"DEBUG: Calling LLM with {len(llm_messages)} messages")
        print(f"DEBUG: Last message: {llm_messages[-1]}")
        
        response = self.llm.invoke(llm_messages)
        
        print(f"DEBUG: LLM response content: '{response.content}'")
        
        # Handle empty response
        if not response.content or response.content.strip() == "":
            print("DEBUG: Empty response from LLM, providing fallback")
            parsed_response = {
                "type": "final_response", 
                "response": "I apologize, but I encountered an issue processing your request. Please try again."
            }
            response_content = json.dumps(parsed_response)
        else:
            response_content = response.content
            # Clean the response content - remove markdown code blocks
            clean_content = response.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            
            # Try to fix incomplete JSON
            if clean_content.startswith('{"type": "tool_calls"') and not clean_content.endswith('}'):
                # Attempt to complete the JSON
                if '"tool_calls": [' in clean_content and not clean_content.endswith('}]}'):
                    clean_content += '}]}'
                    print(f"DEBUG: Attempted to fix incomplete JSON: {clean_content}")
            
            try:
                parsed_response = json.loads(clean_content)
            except Exception as e:
                print(f"DEBUG: JSON parse error: {e}")
                print(f"DEBUG: Attempted to parse: {clean_content}")
                
                parsed_response = {"type": "final_response", "response": response.content}
        
        return {
            "messages": state.messages + [{"role": "assistant", "content": response_content}],
            "last_response": parsed_response
        }
    
    def _execute_tools(self, state: AgentState) -> Dict[str, Any]:
        new_messages = []
        tool_results = []
        
        for i, tool_call in enumerate(state.last_response.get("tool_calls", [])):
            try:
                # Use sync version instead of asyncio.run()
                result = tool_executor_sync(tool_call["name"], tool_call["arguments"])
                new_messages.append({
                    "role": "tool", 
                    "content": f"Tool {tool_call['name']}: {result}",
                    "tool_call_id": f"call_{i}"
                })
                tool_results.append(f"{tool_call['name']}: {result}")
            except Exception as e:
                new_messages.append({
                    "role": "tool", 
                    "content": f"Error: {e}",
                    "tool_call_id": f"call_{i}"
                })
                tool_results.append(f"{tool_call['name']}: Error - {e}")
        
        # Add a user message to prompt the agent to respond with the tool results
        user_prompt = f"Please analyze the following tool results and provide a comprehensive response: {'; '.join(tool_results)}"
        new_messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        return {
            "messages": state.messages + new_messages,
            "last_response": None
        }
    
    def _should_execute_tools(self, state: AgentState) -> str:
        decision = "execute_tools" if state.last_response and state.last_response.get("type") == "tool_calls" else "end"
        print(f"🤔 CONDITIONAL DECISION: {decision}")
        if state.last_response:
            print(f"   Last response type: {state.last_response.get('type')}")
        return decision
    
    def run(self, input_message: str) -> str:
        # Add system prompt only once at the beginning
        initial_state = AgentState(messages=[
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": input_message}
        ])
        
        # Add debug configuration
        config = {"configurable": {"thread_id": "1"}}
        
        print("🚀 STARTING WORKFLOW")
        final_state = self.app.invoke(initial_state, config=config)
        print("🏁 WORKFLOW COMPLETED")
        
        return final_state



if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0, api_key=os.getenv("GOOGLE_API_KEY"))
    tool_descriptions = [{"name": "weather", "description": "Weather forecasts and disaster alerts for agricultural planning", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 40.7128, "lon": -74.006}}]}, {"name": "market", "description": "Fetches mandi prices for agricultural commodities using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "AAPL stock price", "max_results": 5}}]}, {"name": "disease", "description": "Identifies plant diseases from crop images", "inputSchema": {"image_url": "string (URL)"}, "examples": [{"input": {"image_url": "https://example.com/plant.jpg"}}]}, {"name": "soil", "description": "Analyzes soil composition using ISRIC SoilGrids API", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 40.7128, "lon": -74.006}}]}, {"name": "policy", "description": "Agricultural policies and government schemes using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "agricultural subsidies", "max_results": 5}}]}, {"name": "insurance", "description": "Agricultural insurance schemes using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "crop insurance", "max_results": 5}}]}, {"name": "climate", "description": "Provides climate and weather data analysis using Tomorrow.io", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 35.6762, "lon": 139.6503}}]}, {"name": "code_interpreter", "description": "Executes Python code provided by the agent using e2b code interpreter", "inputSchema": {"code": "string (Python code)"}, "examples": [{"input": {"code": "print('Hello World'); x = 5 + 10; print(f'Sum: {x}')"}}]}, {"name": "disaster", "description": "Provides real-time disaster alerts and information for India", "inputSchema": {"country": "string (default: IN)", "limit": "number (1-20, default: 5)"}, "examples": [{"input": {"country": "IN", "limit": 5}}]}]

    agent = AgrifactAgent(llm, tool_descriptions, tool_executor_sync)
    print(agent.run("What is the weather in Tokyo?"))