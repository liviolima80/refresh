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

# import callbacks
from callback import before_tool_callback, after_tool_callback
from callback import before_agent_callback, after_agent_callback

#import agents
from logger_agent import logger_agent
from activity_agent import activity_agent

APP_NAME = "RefreshApp"

# 1. Load Environment Variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEFAULT_CORPUS_NAME = os.getenv("DEFAULT_CORPUS_NAME")
DEFAULT_BUCKET_NAME = os.getenv("DEFAULT_BUCKET_NAME")
DEFAULT_CORPUS_ID = os.getenv("DEFAULT_CORPUS_ID")

if not GOOGLE_API_KEY:
    raise ValueError("Please set your GOOGLE_API_KEY in a .env file or environment variables.")

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Tools definition
def check_login_status(tool_context: ToolContext) -> str:
    """
    Check the application's login status. The reply is formatted in json format.
    if someone logged to the system the reply is '{\"status\": \"logged_in\"}'.
    if nobody logged to the system the reply is '{\"status\": \"logged_out\"}'.
    """
    # Use .get() with a default to avoid KeyErrors
    status = tool_context.state.get('login_status', "False")

    if status == "True":
        return {"status": "logged_in"}
    else:
        return {"status": "logged_out"}

check_login_status_tool = FunctionTool(func=check_login_status)

#important: when you refer a tool name in instruction use 'function_name' tool not the name of FunctionTool variable
# example : use tool 'check_login_status' NOT use tool 'check_login_status_tool'

# Agents definition
root_agent = LlmAgent(
    name="root_agent",
    model="gemini-2.5-flash-lite",  # Or another supported model
    description="You are a strict system router.",
    instruction="You are a strict system router. You are NOT a chat assistant. " \
                "Do not attempt to answer the user's question. Do not analyze the user's intent yet.\n\n" \
                "PROTOCOL FOR EVERY MESSAGE (NO EXCEPTIONS):\n" \
                "1. IGNORE the user's message content.\n" \
                "2. CALL tool `check_login_status` tool immediately.\n" \
                "3. OBSERVE the JSON output:\n" \
                "   - IF `{'status': 'logged_out'}` -> DELEGATE to `logger_agent`.\n"
                "   - IF `{'status': 'logged_in'}` -> DELEGATE to `activity_agent`.\n\n"
                #"   - IF `{'status': 'logged_out'}` -> call tool tool `logger_agent`.\n" \
                #"   - IF `{'status': 'logged_in'}` -> call tool `activity_agent`.\n\n" \
                #"Always forward the user with the tool reply",
                "You must delegate the conversation. Do not reply to the user yourself.",
    sub_agents=[logger_agent, activity_agent],
    tools=[check_login_status_tool],
    #tools=[check_login_status_tool, AgentTool(logger_agent), AgentTool(activity_agent)],
    before_tool_callback=before_tool_callback,  
    after_tool_callback=after_tool_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback   
)

# 2. RUNTIME: Initialize the Runner and Session Service

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)

# 3. API: Create the FastAPI App
app = FastAPI(title="Google ADK Agent API")

# Define the request model
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    reset: Optional[str] = None

# Define the endpoint
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Send a message to the agent and get a response.
    Maintains context using the provided session_id.
    """
    try:

        initial_state = {
                        "login_status": "False",
                        "username": "",
                        "user_id": "0",
                        "session_id": "0",
                        "bucket_name": DEFAULT_BUCKET_NAME,
                        "corpus_name": DEFAULT_CORPUS_NAME,
                        "corpus_id": DEFAULT_CORPUS_ID
                        }

        text = ""
            
        # Run the agent asynchronously
        # The runner handles the conversation history automatically based on session_id

        # 1. Determine the Session ID
        # If client didn't send one, generate a new UUID
        current_session_id = request.session_id if (request.session_id and request.session_id != "0") else str(uuid.uuid4())
        current_user_id = request.user_id if (request.user_id and request.user_id != "0") else "0"

        if current_user_id == "0":
            # happens before the login
            try:
                session = await session_service.create_session( app_name=APP_NAME, user_id=current_user_id, session_id=current_session_id, state=initial_state)
                print("CREATE A NEW SESSION BEFORE LOGIN")
            except:
                session = await session_service.get_session( app_name=APP_NAME, user_id=current_user_id, session_id=current_session_id )
                print("LOAD A PREVIOUS SESSION DURING LOGIN")
        else:
            # WORKAROUND WITH SUB-AGENTS
            # sub-agent works better because keep session context. The drawback is that it maintains the control of the conversation.
            # in order to restart from parent agent I need to restart the session
            
            if request.reset and request.reset == "True":
                # case 1: after a study session start a new session with a different session_id
                # in this way the control move back from question_agent to root_agent
                initial_state['session_id'] = str(uuid.uuid4())
                initial_state['user_id'] = current_user_id
                initial_state['login_status'] = "True"
            else:
                # case 2: after the login start a new session changing the user_id
                # in this way the control move back from logger_agent to root_agent
                initial_state['session_id'] = current_session_id
                initial_state['user_id'] = current_user_id
                initial_state['login_status'] = "True"
            
            try:
                session = await session_service.create_session( app_name=APP_NAME, user_id=current_user_id, session_id=current_session_id, state=initial_state)
                print("CREATE A NEW SESSION AFTER LOGIN")
            except:
                session = await session_service.get_session( app_name=APP_NAME, user_id=current_user_id, session_id=current_session_id )
                print("LOAD A PREVIOUS SESSION AFTER LOGIN")

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
        await session_service.append_event(session, system_event)
        print(f"State after event: {session.state}")

        '''
        print(f"--- Examining Session Properties ---")
        print(f"ID (`id`):                          {session.id}")
        print(f"Application Name (`app_name`):      {session.app_name}")
        print(f"User ID (`user_id`):                {session.user_id}")
        print(f"State (`state`):                    {session.state}") # Note: Only shows initial state here
        print(f"Events (`events`):                  {session.events}") # Initially empty
        print(f"Last Update (`last_update_time`):   {session.last_update_time:.2f}")
        print(f"---------------------------------")
        '''

        print(f"DEBUG: Running agent as User: {session.user_id} | Session: {session.id}")

        query_content = types.Content(role="user", parts=[types.Part(text=request.message)])

        async for event in runner.run_async( user_id=session.user_id, session_id=session.id, new_message=query_content ):
            if event.is_final_response() and event.content and event.content.parts:
                text = event.content.parts[0].text
                print(text)

        # reload session in order to get the updated state
        session = await session_service.get_session( app_name=APP_NAME, user_id=current_user_id, session_id=current_session_id )

        return {
            "response": text, 
            "session_id": session.state.get("session_id"),
            "user_id": session.state.get("user_id"),
            "login_status": session.state.get("login_status")
        }
    
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)