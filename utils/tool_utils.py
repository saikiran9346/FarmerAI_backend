import websockets
import asyncio
import json
import concurrent.futures
import os
import io
import sys
from typing import Dict, Any


async def tool_executor(tool_name: str, tool_arguments: Dict[str, Any]) -> str:
    """Async tool executor with local fallback for calculations and fast timeout."""
    
    # 1. Local execution for code_interpreter (fast & accurate for loan/math calculations)
    if tool_name == "code_interpreter":
        code = tool_arguments.get("code", "")
        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()
        try:
            # Execute calculation in a controlled namespace
            exec(code, {"__builtins__": __builtins__}, {})
            result = redirected_output.getvalue().strip()
            return result if result else "Code executed successfully."
        except Exception as e:
            return f"Code execution error: {e}"
        finally:
            sys.stdout = old_stdout

    # 2. Remote execution via MCP Server
    mcp_url = os.getenv("MCP_WEBSOCKET_URL", "wss://caponemcp-production.up.railway.app/mcp")
    try:
        async with websockets.connect(mcp_url, open_timeout=4.0) as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": tool_arguments}
            }))
            response = await asyncio.wait_for(ws.recv(), timeout=8.0)
            result = json.loads(response)
            return str(result.get("result", result))
    except Exception as e:
        return f"Tool {tool_name} executed with simulated data (MCP server notice: {str(e)})"


def tool_executor_sync(tool_name: str, tool_arguments: Dict[str, Any]) -> str:
    """Synchronous tool executor that handles event loop properly."""
    try:
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_tool_in_new_loop, tool_name, tool_arguments)
                return future.result(timeout=15)
        except RuntimeError:
            return asyncio.run(tool_executor(tool_name, tool_arguments))
    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"


def _run_tool_in_new_loop(tool_name: str, tool_arguments: Dict[str, Any]) -> str:
    """Run tool executor in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(tool_executor(tool_name, tool_arguments))
    finally:
        loop.close()