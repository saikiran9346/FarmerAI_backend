"""Configuration settings for CapOne Agents."""

import os
import asyncio
import websockets
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class AgentConfig(BaseModel):
    """Configuration for CapOne Agents."""
    
    # LLM Configuration
    model_name: str = "gemini-2.0-flash"
    max_output_tokens: int = 1024
    
    # API Configuration
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    mcp_websocket_url: str = "wss://caponemcp-production.up.railway.app/mcp"
    
    # Tool Configuration
    tool_descriptions: List[Dict[str, Any]] = []
    
    # Debug Configuration
    debug_mode: bool = False
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables."""
        return cls(
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            model_name=os.getenv("MODEL_NAME", "gemini-2.0-flash"),
            max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "1024")),
            debug_mode=os.getenv("DEBUG", "false").lower() == "true",
            mcp_websocket_url=os.getenv("MCP_WEBSOCKET_URL", "wss://caponemcp-production.up.railway.app/mcp")
        )
    
    async def fetch_tools(self) -> List[Dict[str, Any]]:
        """Fetch tool descriptions from MCP server."""
        try:
            async with websockets.connect(self.mcp_websocket_url) as ws:
                # Send tools/list request
                list_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                }
                await ws.send(json.dumps(list_msg))
                response = await ws.recv()
                
                # Parse response
                response_data = json.loads(response)
                
                if "result" in response_data and "tools" in response_data["result"]:
                    tools = response_data["result"]["tools"]
                    
                    # Transform to our expected format
                    tool_descriptions = []
                    for tool in tools:
                        tool_desc = {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "inputSchema": tool.get("inputSchema", {})
                        }
                        tool_descriptions.append(tool_desc)
                    
                    return tool_descriptions
                else:
                    print(f"Unexpected response format: {response_data}")
                    return self._get_fallback_tools()
                    
        except Exception as e:
            print(f"Error fetching tools from MCP server: {e}")
            return self._get_fallback_tools()
    
    def get_tools_sync(self, loop=None) -> List[Dict[str, Any]]:
        """Synchronous wrapper to fetch tools with proper event loop handling."""
        try:
            # Check if we're in an async context
            try:
                current_loop = asyncio.get_running_loop()
                # We're in an async context, create a new thread to run the async function
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_fetch_tools_in_new_loop)
                    return future.result(timeout=30)  # 30 second timeout
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                return asyncio.run(self.fetch_tools())
        except Exception as e:
            print(f"Error in sync tool fetch: {e}")
            return self._get_fallback_tools()
    
    def _run_fetch_tools_in_new_loop(self) -> List[Dict[str, Any]]:
        """Run fetch_tools in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.fetch_tools())
        finally:
            loop.close()
    
    def _get_fallback_tools(self) -> List[Dict[str, Any]]:
        """Fallback tool descriptions in case MCP server is unavailable."""
        return [
            {
                "name": "weather",
                "description": "Weather forecasts and disaster alerts for agricultural planning",
                "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}
            },
            {
                "name": "market", 
                "description": "Fetches mandi prices for agricultural commodities",
                "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}
            },
            {
                "name": "soil",
                "description": "Analyzes soil composition using ISRIC SoilGrids API",
                "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}
            },
            {
                "name": "policy",
                "description": "Agricultural policies and government schemes",
                "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}
            },
            {
                "name": "insurance",
                "description": "Agricultural insurance schemes",
                "inputSchema": {"query": "string", "max_results": "number (1-20, default: 5)"}
            },
            {
                "name": "climate",
                "description": "Climate and weather data analysis",
                "inputSchema": {"lat": "number (-90 to 90)", "lon": "number (-180 to 180)"}
            },
            {
                "name": "code_interpreter",
                "description": "Executes Python code using e2b code interpreter",
                "inputSchema": {"code": "string (Python code)"}
            },
            {
                "name": "disaster",
                "description": "Real-time disaster alerts and information",
                "inputSchema": {"country": "string (default: IN)", "limit": "number (1-20, default: 5)"}
            }
        ]

    # Keep the old method for backward compatibility but mark as deprecated
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tool descriptions (deprecated - use get_tools_sync() instead)."""
        return self.get_tools_sync()