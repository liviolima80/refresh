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

from callback import before_tool_callback, after_tool_callback
from callback import before_agent_callback, after_agent_callback

from rag_tools import import_document_to_corpus_tool, retrieve_context_tool
from gcs_tools import list_gcs_buckets_tool, list_blobs_in_bucket_tool

from question_agent import question_agent_tool

activity_agent = LlmAgent(
    name="activity_agent",
    model="gemini-2.5-pro",  # Or another supported model
    description="you respond to user after login",
    instruction= "**ROLE**\n" \
                 "You are the agent responsible to interact with a student after the login. You will help students with their study sessions. \n" \
                 "**INITIAL INTERACTION**\n" \
                 "Greet the user and present these three options:\n" \
                 "1.  **List files** List the files available in Google Cloud Storage (GCS) bucket. " \
                 "2.  **Import file** Import a file from Google Cloud Storage (GCS) bucket to RAG corpus. \n" \
                 "3.  **Create question** Create a question based on user prompt and RAG Searching. \n" \
                 "**COMMAND LOGIC**\n" \
                 "Identify the user's intent and perform one of the following actions:\n" \
                 "- If the user select option 1. call tool 'list_blobs_in_bucket' passing 'bucket_name'={bucket_name}. "\
                 " Then Always parse the tool output extract the list of blobs with size less than 7000000 and present them to the user. \n" \
                 "- If the user select option 2 ask for the filename to import. "\
                 " Then call tool 'import_document_to_corpus' passing 'bucket_name'={bucket_name}, 'corpus_id'={corpus_id} and 'file_name' equal to the filename selected by the user. \n" \
                 "- If the user select option 3 always call tool 'question_agent' and ask the tool to create a question. \n" \
                 "**ERROR HANDLING**\n" \
                 "If the user requests an operation not listed above, reply: 'I can only assist with the three supported operations. Please select 1, 2, or 3.'",
    tools = [list_blobs_in_bucket_tool, import_document_to_corpus_tool, question_agent_tool],
    before_tool_callback=before_tool_callback,  
    after_tool_callback=after_tool_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback  
)

import asyncio

if __name__ == "__main__":
    
    APP_NAME = "RefreshApp"

    # 1. Load Environment Variables
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    DEFAULT_CORPUS_NAME = os.getenv("DEFAULT_CORPUS_NAME")
    DEFAULT_BUCKET_NAME = os.getenv("DEFAULT_BUCKET_NAME")
    DEFAULT_CORPUS_ID = os.getenv("DEFAULT_CORPUS_ID")

    initial_state = {
        "login_status": "False",
        "username": "",
        "user_id": "0",
        "session_id": "0",
        "bucket_name": DEFAULT_BUCKET_NAME,
        "corpus_name": DEFAULT_CORPUS_NAME,
        "corpus_id": DEFAULT_CORPUS_ID
    }

    session_service = InMemorySessionService()

    runner = Runner(agent=activity_agent, session_service=session_service, app_name=APP_NAME)

    current_session_id = str(uuid.uuid4())

    async def fetch_data(current_session_id, initial_state):
        session = await session_service.create_session( app_name=APP_NAME, user_id="0", session_id=current_session_id, state=initial_state)
        return session

    session = asyncio.run(fetch_data(current_session_id, initial_state))    

    # --- Create Event with Actions ---
    state_changes = {
        "session_id": session.id,
        "bucket_name": DEFAULT_BUCKET_NAME,
        "corpus_id": DEFAULT_CORPUS_ID
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