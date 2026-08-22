import websockets
import asyncio
import json
import concurrent.futures
from typing import Dict, Any


async def tool_executor(tool_name: str, tool_arguments: Dict[str, Any]) -> str:
    """Async tool executor for use in async contexts."""
    async with websockets.connect("wss://caponemcp-production.up.railway.app/mcp") as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": tool_arguments}
        }))
        response = await ws.recv()
        result = json.loads(response)
        return str(result.get("result", result))


def tool_executor_sync(tool_name: str, tool_arguments: Dict[str, Any]) -> str:
    """Synchronous tool executor that handles event loop properly."""
    try:
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, need to use a thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_tool_in_new_loop, tool_name, tool_arguments)
                return future.result(timeout=30)
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
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