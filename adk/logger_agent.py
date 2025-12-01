import os
import uvicorn
import uuid
import time
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from typing import Dict, Any, Optional

# Google ADK imports
from google.adk.agents import LlmAgent, Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.google_llm import Gemini
from google.adk.events import Event, EventActions
from google.adk.runners import Runner, InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import load_memory, preload_memory, AgentTool, BaseTool, FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# to use MCP Toolbox for Database
from toolbox_core import ToolboxSyncClient

# import callbacks
from callback import before_tool_callback, after_tool_callback
from callback import before_agent_callback, after_agent_callback

# DEFINE THE FUNCTION TOOLS

def update_username(username: str, tool_context: ToolContext)-> str:
    """
    Update active username with the provided arguments. Always reply with '{\"status\": \"ok\"}'
    """
    print("update_username : user = |", username)
    tool_context.state['username'] = username

    return "{\"status\": \"ok\"}"

def get_active_user(tool_context: ToolContext) -> str:
    """
    Reply with the username and email of the active user. Always reply with a json string formatted as follow
    {
        "username": "user",
        "email": "mail"
    }
    """
    return "{\"username\": \"" + tool_context.state.get('username', "") + "\"," \
             "\"email\": \"" + tool_context.state.get('email', "") + "\"}"
    
def update_login(student_id: int, guid: str, tool_context: ToolContext) -> str:
    """
    Update login information with the provided arguments. Always reply with '{\"status\": \"ok\"}'
    """

    print("update_login : user = |", str(student_id), "| session = |" , guid)
    
    tool_context.state['user_id'] = str(student_id)
    tool_context.state['session_id'] = guid

    if str(student_id) != "0" and guid != "0":
        tool_context.state['login_status'] = "True"
        print("LOGIN TRUE")
    else:
        tool_context.state['login_status'] = "False"
        print("LOGIN FALSE")

    return "{\"status\": \"ok\"}"

update_login_tool = FunctionTool(func=update_login)
update_username_tool = FunctionTool(func=update_username)
get_active_user_tool = FunctionTool(func=get_active_user)

# DEFINE THE MCP TOOLS
# 2. connect to MCP Toolbox server
load_dotenv()
MCP_TOOLBOX_URL = os.getenv("MCP_TOOLBOX_URL")
toolbox = ToolboxSyncClient(MCP_TOOLBOX_URL)
mcp_tools = toolbox.load_toolset('login-toolset')

# 3. create Agents
# remember to keep attention to punctuation and spaces between each sentence
# otherwise the agent can confuse the instructions

logger_agent = LlmAgent(
    name="logger_agent",
    model="gemini-2.5-flash-lite",  # Or another supported model
    description="you respond to user after login",
    instruction= "You are the agent responsible to manage the login process of the student. \n" \
                 "You have to follow the following PROTOCOL FOR EVERY MESSAGE (NO EXCEPTIONS):\n" \
                 "STEP 1. call 'get_active_user' tool. OBSERVE the JSON output:\n"
                 " -If parameter 'username' is equal to '' ask for the username. Mandatory: call 'update_username' tool with the reply provided. \n" \
                 " -If parameter 'username' is NOT equal to '' skip to step 2. \n" \
                 "STEP 2. Use the appropriate tool to get student info. convert the username to lowercase before using tools.\n" \
                 " -if the student exists you will receive student's data in json format. skip to step 4. \n" \
                 " -if the student does not exist you will receive null reply. go to step 3. \n" \
                 "STEP 3. Ask for the student's email. Mandatory: use the appropriate tool to add the student. Use the provided username as argument.\n" \
                 "STEP 4. Use the appropriate tool to get the last session for the student. provide the student id you retrieved: \n" \
                 " -If the session exists you will receive session's data in json format. go to step 5. \n" \
                 " -If the session does not exist you will receive null reply. ask for a session name and use 'add-session' tool to add a new session. Argument guid={session_id}. \n" \
                "STEP 5. Call 'update_login' tool to update active login information. \n" \
                "STEP 6. Reply with a message confirming the login and session name. \n",
    tools=mcp_tools + [get_active_user_tool, update_login_tool, update_username_tool],
    before_tool_callback=before_tool_callback,  
    after_tool_callback=after_tool_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback  
)

import asyncio

# Main function in order to test the single agent
if __name__ == "__main__":
    
    APP_NAME = "RefreshApp"

    # 1. Load Environment Variables
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    DEFAULT_CORPUS_NAME = os.getenv("DEFAULT_CORPUS_NAME")
    DEFAULT_BUCKET_NAME = os.getenv("DEFAULT_BUCKET_NAME")

    initial_state = {
        "login_status": "False",
        "username": "",
        "user_id": "0",
        "session_id": "0",
        "bucket_name": DEFAULT_BUCKET_NAME,
        "corpus_name": DEFAULT_CORPUS_NAME
    }

    session_service = InMemorySessionService()

    runner = Runner(agent=logger_agent, session_service=session_service, app_name=APP_NAME)

    current_session_id = str(uuid.uuid4())

    async def fetch_data(current_session_id, initial_state):
        session = await session_service.create_session( app_name=APP_NAME, user_id="0", session_id=current_session_id, state=initial_state)
        return session

    session = asyncio.run(fetch_data(current_session_id, initial_state))    

    # --- Create Event with Actions ---
    state_changes = {
        "session_id": session.id
    }
    actions_with_update = EventActions(state_delta=state_changes)
    # This event might represent an internal system action, not just an agent response
    system_event = Event(
        invocation_id="inv_login_update",
        author="system", # Or 'agent', 'tool' etc.
        actions=actions_with_update,
        timestamp=time.time()
        # content might be None or represent the action taken
    )
    # --- Append the Event (This updates the state) ---
    asyncio.run(session_service.append_event(session, system_event))

    print(f"--- Examining Session Properties ---")
    print(f"ID (`id`):                          {session.id}")
    print(f"Application Name (`app_name`):      {session.app_name}")
    print(f"User ID (`user_id`):                {session.user_id}")
    print(f"State (`state`):                    {session.state}") # Note: Only shows initial state here
    print(f"Events (`events`):                  {session.events}") # Initially empty
    print(f"Last Update (`last_update_time`):   {session.last_update_time:.2f}")
    print(f"---------------------------------")

    while(True):

        message = input("user input ["+session.state.get("session_id")+"]: ")
        if message == "quit":
            break

        query_content = types.Content(role="user", parts=[types.Part(text=message)])

        for event in runner.run( user_id="0", session_id=session.id, new_message=query_content ):
            if event.is_final_response() and event.content and event.content.parts:
                text = event.content.parts[0].text
                print("AI reply: " + text)