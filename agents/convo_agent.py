from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, Optional, Dict, Any, Callable, Tuple
from pydantic import BaseModel
from datetime import datetime
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
from agents.financial_agent import FinancialAgent
from agents.agrifact_agent import AgrifactAgent

class ConvoState(BaseModel):
    messages: List[Dict[str, str]] = []
    last_response: Optional[Dict[str, Any]] = None

class ConversationalAgent:
    def __init__(self, model_name: str, tool_descriptions: List[Dict], tool_executor_func: Callable):
        self.tool_descriptions = tool_descriptions
        self.model_name = model_name
        self.tool_executor = tool_executor_func

        if model_name.startswith("gemini"):
            self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0, api_key=os.getenv("GOOGLE_API_KEY"))
        elif model_name.startswith("gpt"):
            self.llm = ChatOpenAI(model=model_name, temperature=0.0, api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise ValueError(f"Invalid LLM name: {model_name}")
        
        # Initialize sub-agents
        self.financial_agent = FinancialAgent(self.llm, tool_descriptions, tool_executor_func)
        self.agrifact_agent = AgrifactAgent(self.llm, tool_descriptions, tool_executor_func)
        
        self.system_prompt = self._build_system_prompt()
        self.app = self.build_workflow()

        # REMOVED: No more shared conversation_state!
        # This makes the agent stateless and thread-safe
    
    def _build_system_prompt(self) -> str:
        return """You are a friendly conversational assistant that helps farmers with both financial and agricultural needs. 

You have access to two specialized agents:
1. financial_agent - for complex financial calculations, loans, EMI, budgeting, insurance costs
2. agrifact_agent - for detailed agricultural information, weather data, soil analysis, crop diseases, policies

When responding with the final response after analysing agent's response, do not mention anything related to the agent's response in the final response. 

CRITICAL: You must respond with ONLY valid JSON. No markdown formatting, no code blocks, no extra text.

OUTPUT FORMATS:

For delegating to agents (only for complex queries needing specialized tools):
{"type": "agent_call", "agent": "financial_agent", "query": "user's financial question"}
{"type": "agent_call", "agent": "agrifact_agent", "query": "user's agricultural question"}

For direct response and final response after agent calls:
{"type": "final_response", "response": "the final response to the user"}

IMPORTANT: The final response should be a JSON object with the type "final_response" and the response field containing the final response to the user.

DECISION GUIDELINES:
- Use agents ONLY for complex queries requiring calculations or external data
- Handle simple questions, greetings, and general conversation with direct responses
- Financial agent: loan calculations, EMI, interest rates, complex budgeting, financial planning
- Agrifact agent: weather forecasts, soil analysis, crop diseases, government policies, image analysis
- Direct response: greetings, basic farming advice, general tips, simple questions

SPECIAL CASES:
- Image uploads → always use agrifact_agent
- File uploads → always use agrifact_agent  
- Weather queries → use agrifact_agent
- Disease diagnosis → use agrifact_agent
- Loan/EMI calculations → use financial_agent

EXAMPLES:
- "Hello" → {"type": "final_response", "response": "Hello! I'm here to help with your farming and financial needs..."}
- "What is crop rotation?" → {"type": "final_response", "response": "Crop rotation is the practice of..."}
- "Calculate EMI for 5 lakh loan" → {"type": "agent_call", "agent": "financial_agent", "query": "Calculate EMI for 5 lakh loan"}
- "What's the weather forecast?" → {"type": "agent_call", "agent": "agrifact_agent", "query": "What's the weather forecast?"}

Remember: Return ONLY the JSON object, nothing else.

LANGUAGE RULE (CRITICAL):
- Always detect the language of the user's message (Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, English, etc.).
- Always respond in the EXACT SAME language the user used.
- If user writes in Telugu → respond in Telugu.
- If user writes in Hindi → respond in Hindi.
- If user writes in Tamil → respond in Tamil.
- If user writes in Kannada → respond in Kannada.
- If user writes in Malayalam → respond in Malayalam.
- If user writes in Marathi → respond in Marathi.
- If user writes in Bengali → respond in Bengali.
- If user writes in Gujarati → respond in Gujarati.
- If user writes in Punjabi → respond in Punjabi.
- If user writes in English → respond in English.
- If user asks in any other regional/global language, respond in that exact language.
- Never mix languages unless the user does so first."""

    def build_workflow(self):
        def debug_node(node_name):
            def wrapper(func):
                def inner(*args, **kwargs):
                    print(f" ENTERING NODE: {node_name}")
                    result = func(*args, **kwargs)
                    print(f" EXITING NODE: {node_name}")
                    return result
                return inner
            return wrapper
        
        workflow = StateGraph(ConvoState)
        workflow.add_node("call_orchestrator", debug_node("call_orchestrator")(self._call_orchestrator))
        workflow.add_node("call_agent", debug_node("call_agent")(self._call_agent))
        workflow.set_entry_point("call_orchestrator")
        workflow.add_conditional_edges(
            "call_orchestrator",
            self._should_call_agent,
            {"call_agent": "call_agent", "end": END}
        )
        workflow.add_edge("call_agent", "call_orchestrator")
        # return workflow.compile().with_config(config={"callbacks": [self.langfuse_handler]})
        return workflow.compile()
    
    def _call_orchestrator(self, state: ConvoState) -> Dict[str, Any]:
        llm_messages = state.messages
        
        print(f"DEBUG: Calling orchestrator with {len(llm_messages)} messages")
        print(f"DEBUG: Last message: {llm_messages[-1] if llm_messages else 'No messages'}")
        
        response = self.llm.invoke(llm_messages)
        
        print(f"DEBUG: Orchestrator response: '{response.content}'")
        
        # Clean and parse response
        clean_content = response.content.strip()
        
        # Remove markdown code blocks if present
        if clean_content.startswith("```json"):
            clean_content = clean_content.removeprefix("```json").removesuffix("```").strip()
        elif clean_content.startswith("```"):
            clean_content = clean_content.removeprefix("```").removesuffix("```").strip()
        
        print(f"DEBUG: Clean content to parse: '{clean_content}'")
        
        try:
            parsed_response = json.loads(clean_content)
            print(f"DEBUG: Successfully parsed JSON: {parsed_response}")
        except Exception as e:
            print(f"DEBUG: JSON parse error: {e}")
            print(f"DEBUG: Failed to parse: '{clean_content}'")
            # Make a fallback LLM call to get a simple response
            fallback_messages = [
                {"role": "system", "content": "Return the final response as string and nothing else."},
                {"role": "user", "content": f"{clean_content}"}
            ]
            fallback_response = self.llm.invoke(fallback_messages)
            parsed_response = {"type": "final_response", "response": fallback_response.content}
            print(f"DEBUG: Fallback LLM response: {fallback_response.content}")
            # Fallback: treat the response as a direct final response
            parsed_response = {"type": "final_response", "response": fallback_response.content}
            print(f"DEBUG: Using fallback parsed_response: {parsed_response}")
        
        # Store the clean JSON content in the message for consistency
        content_to_store = json.dumps(parsed_response) if parsed_response else response.content
        
        return {
            "messages": state.messages + [{"role": "assistant", "content": content_to_store}],
            "last_response": parsed_response
        }
    
    def _call_agent(self, state: ConvoState) -> Dict[str, Any]:
        agent_name = state.last_response.get("agent")
        query = state.last_response.get("query")
        
        print(f"DEBUG: Calling {agent_name} with query: {query}")
        
        try:
            if agent_name == "financial_agent":
                result = self.financial_agent.run(query)
                # Extract final response from the result
                if isinstance(result, dict) and result.get("last_response", {}).get("response"):
                    agent_result = result["last_response"]["response"]
                else:
                    agent_result = str(result)
            elif agent_name == "agrifact_agent":
                result = self.agrifact_agent.run(query)
                # Extract final response from the result
                if isinstance(result, dict) and result.get("last_response", {}).get("response"):
                    agent_result = result["last_response"]["response"]
                else:
                    agent_result = str(result)
            else:
                agent_result = f"Unknown agent: {agent_name}"
            
            print(f"DEBUG: Agent result type: {type(agent_result)}")
            print(f"DEBUG: Agent result preview: {str(agent_result)[:200]}...")
            
            # Check if agent_result is a JSON string that needs parsing
            if isinstance(agent_result, str) and agent_result.strip().startswith('{"type":'):
                try:
                    parsed_agent_result = json.loads(agent_result)
                    if parsed_agent_result.get("type") == "final_response":
                        actual_response = parsed_agent_result.get("response", agent_result)
                        print(f"DEBUG: Extracted nested response: {actual_response[:200]}...")
                        agent_result = actual_response
                except json.JSONDecodeError:
                    print(f"DEBUG: Failed to parse agent result as JSON, using as-is")
                    pass
            
            # Add agent result as a user message to prompt orchestrator to respond
            user_prompt = (
                f"The {agent_name} provided this information: {agent_result}. "
                f"CRITICAL LANGUAGE RULE: Formulate a comprehensive, helpful final response to the user based on this information. "
                f"You MUST respond in the EXACT SAME LANGUAGE that the user originally asked in (e.g., if the user asked in Telugu, answer entirely in Telugu; if in Hindi, answer in Hindi; if in English, answer in English). "
                f"Respond with a final_response JSON only: {{\"type\": \"final_response\", \"response\": \"your response in user's language\"}}"
            )
            
            return {
                "messages": state.messages + [
                    {"role": "user", "content": user_prompt}
                ],
                "last_response": None
            }
            
        except Exception as e:
            print(f"DEBUG: Error calling agent: {e}")
            error_prompt = f"There was an error calling {agent_name}: {e}. Please provide a helpful response to the user."
            return {
                "messages": state.messages + [{"role": "user", "content": error_prompt}],
                "last_response": None
            }
    
    def _should_call_agent(self, state: ConvoState) -> str:
        if not state.last_response:
            return "end"
            
        response_type = state.last_response.get("type")
        decision = "call_agent" if response_type == "agent_call" else "end"
        
        print(f" CONDITIONAL DECISION: {decision}")
        print(f"   Response type: {response_type}")
        
        if response_type == "agent_call":
            print(f"   Will call: {state.last_response.get('agent')}")
        elif response_type == "final_response":
            print(f"   Direct response provided")
        
        return decision
    
    def run_with_context(self, input_message: str, conversation_history: List[Dict[str, str]], previous_summary: Optional[str] = None, new_conversation: bool = False) -> Tuple[str, List[Dict[str, str]]]:
        """
        Run agent with provided conversation context.
        
        Args:
            input_message: User's input message
            conversation_history: Previous messages from Redis
            previous_summary: Previous conversation summary
            
        Returns:
            tuple: (agent_response, new_messages_to_save)
        """
        print(" STARTING CONVERSATIONAL WORKFLOW (STATELESS)")
        
        # Build complete context
        messages = []
        
        # Add system prompt with summary context
        system_content = self.system_prompt
        if previous_summary:
            system_content += f"\n\nPrevious conversation summary: {previous_summary}"
        
        messages.append({"role": "system", "content": system_content})
        
        # Add conversation history (last 10 messages from Redis)
        messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": input_message})
        
        # Create temporary state for this request only
        temp_state = ConvoState(
            messages=messages,
            last_response=None
        )
        
        print(f"DEBUG: Processing with {len(messages)} messages")
        
        # Run the workflow
        final_state = self.app.invoke(temp_state, config={"configurable": {"thread_id": f"temp_{hash(input_message)}"}})

        print("CONVERSATIONAL WORKFLOW COMPLETED (STATELESS)")
        
        # Extract the final response
        response = self._extract_final_response(final_state)
        
        # Return new messages that need to be saved to Redis
        new_messages = [
            {"role": "user", "content": input_message, "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
        ]

        if new_conversation:
            title, description = self.generate_title_description(new_messages)
        else:
            title, description = None, None
        
        return response, new_messages, title, description
    
    def _extract_final_response(self, final_state: Dict[str, Any]) -> str:
        """Extract the final response from the workflow state."""
        print(f"DEBUG: Extracting final response from state")
        print(f"DEBUG: last_response = {final_state.get('last_response')}")
        
        # Check if we have a parsed last_response
        if final_state.get("last_response") and final_state["last_response"].get("type") == "final_response":
            response = final_state["last_response"]["response"]
            print(f"DEBUG: Found parsed final_response: {response[:100]}...")
            
            # Check if response is double-encoded JSON
            if isinstance(response, str) and response.strip().startswith('{"type":'):
                try:
                    nested_response = json.loads(response)
                    if nested_response.get("type") == "final_response":
                        actual_response = nested_response.get("response", response)
                        print(f"DEBUG: Extracted double-encoded response: {actual_response[:100]}...")
                        return actual_response
                except json.JSONDecodeError:
                    pass
            
            return response
        
        # Find the last assistant message and try to parse it
        for msg in reversed(final_state["messages"]):
            if msg["role"] == "assistant":
                content = msg["content"]
                print(f"DEBUG: Trying to parse assistant message: {content[:100]}...")
                
                # Clean the content - remove markdown code blocks if present
                clean_content = content.strip()
                if clean_content.startswith("```json"):
                    clean_content = clean_content.removeprefix("```json").removesuffix("```").strip()
                elif clean_content.startswith("```"):
                    clean_content = clean_content.removeprefix("```").removesuffix("```").strip()
                
                try:
                    response_data = json.loads(clean_content)
                    if response_data.get("type") == "final_response":
                        response = response_data["response"]
                        print(f"DEBUG: Successfully parsed JSON final_response: {response[:100]}...")
                        return response
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON parse error for message: {e}")
                    # If parsing fails, but content looks like it might be the actual response text
                    # (not JSON), return it directly
                    if not clean_content.startswith("{") and len(clean_content) > 10:
                        print(f"DEBUG: Returning content as-is (not JSON): {clean_content[:100]}...")
                        return clean_content
                    continue
                except Exception as e:
                    print(f"DEBUG: Other error parsing message: {e}")
                    continue
        
        print("DEBUG: No valid response found, returning fallback")
        return "I apologize, but I couldn't generate a proper response. Please try again."
        
    def generate_title_description(self, conversation_history: List[Dict[str, str]]) -> Tuple[str, str]:
        """Generate a title and description for the conversation."""
        system_prompt = """"
        You will be given a conversation history and you need to generate a title and description for the conversation.
        The title should be a single sentence (at max 5 words without articles) that captures the essence of the conversation.
        The description should be a detailed description of the conversation (at max 20 words).
        The title and description should be formatted as JSON and returned in the following format with no markdown or code blocks:
        ```json
        {{"title": "title", "description": "description"}}
        ```
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Conversation history: {conversation_history}"}
        ]
        response = self.llm.invoke(messages)
        print(f"DEBUG: Title and description response: {response.content}")
        response_content = response.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            response_data = json.loads(response_content)
            return response_data.get("title"), response_data.get("description")
        except:
            return "New Conversation", "This is a new conversation"

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    tool_descriptions = [{"name": "weather", "description": "Weather forecasts and disaster alerts for agricultural planning. Accepts coordinates or location names.", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 40.7128, "lon": -74.006}}]}, {"name": "market", "description": "Fetches mandi prices for agricultural commodities using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "AAPL stock price", "max_results": 5}}]}, {"name": "disease", "description": "Identifies plant diseases from crop images", "inputSchema": {"image_url": "string (URL)"}, "examples": [{"input": {"image_url": "https://example.com/plant.jpg"}}]}, {"name": "soil", "description": "Analyzes soil composition using ISRIC SoilGrids API. Accepts coordinates or location names.", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 40.7128, "lon": -74.006}}]}, {"name": "policy", "description": "Agricultural policies and government schemes using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "agricultural subsidies", "max_results": 5}}]}, {"name": "insurance", "description": "Agricultural insurance schemes using AI search", "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}, "examples": [{"input": {"query": "crop insurance", "max_results": 5}}]}, {"name": "climate", "description": "Provides climate and weather data analysis using Tomorrow.io. Accepts coordinates or location names.", "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}, "examples": [{"input": {"lat": 35.6762, "lon": 139.6503}}]}, {"name": "code_interpreter", "description": "Executes Python code provided by the agent using e2b code interpreter", "inputSchema": {"code": "string (Python code)"}, "examples": [{"input": {"code": "print('Hello World'); x = 5 + 10; print(f'Sum: {x}')"}}]}, {"name": "geocoding", "description": "Convert location names to latitude and longitude coordinates for agricultural planning", "inputSchema": {}, "examples": []}, {"name": "disaster", "description": "Provides real-time disaster alerts and information for India", "inputSchema": {"country": "string (default: IN)", "limit": "number (1-20, default: 5)"}, "examples": [{"input": {"country": "IN", "limit": 5}}]}]

    convo_agent = ConversationalAgent("gemini-2.5-flash", tool_descriptions, tool_executor_sync)
    
    # Test with different types of queries (using stateless approach)
    print("=== TESTING STATELESS AGENT ===")
    response, new_messages, title, description = convo_agent.run_with_context(
        "Hello, how can you help me?", 
        [],  # Empty conversation history
        None  # No previous summary
    )
    print(f"Response: {response}")
    print(f"New messages to save: {new_messages}")
    print(f"Title: {title}")
    print(f"Description: {description}")
