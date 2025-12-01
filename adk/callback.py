from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext, CallbackContext
from typing import Dict, Any, Optional

async def before_tool_callback(
            tool: BaseTool,
            args: dict[str, Any],
            tool_context: ToolContext
            ):
    print(f"\n[TOOL IN] 🛠️ CALLING TOOL: {tool.name}")
    print(f"[TOOL IN] 📥 ARGUMENTS: {args}")
    print(f"[TOOL IN] 📥 INVOCATION: {tool_context}")
    print("----------------------------------------------------")
    # You can even modify args here if needed for testing

async def after_tool_callback(
            tool: BaseTool,
            tool_response: Dict[str, Any],
            args: dict[str, Any],
            tool_context: ToolContext
            ):
    try:
        print(f"[TOOL OUT] 📤 RESULT from {tool.name}: {tool_response}\n")
        print("----------------------------------------------------")
    except Exception as e:
        print(e)

async def before_agent_callback(
            callback_context: CallbackContext
            ):
    print(f"\n[AGENT IN] : {callback_context.agent_name}")
    print("----------------------------------------------------")

async def after_agent_callback(
            callback_context: CallbackContext
            ):
    print(f"\n[AGENT OUT] : {callback_context.agent_name}s")