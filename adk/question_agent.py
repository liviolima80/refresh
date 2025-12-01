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

question_agent = Agent(
    name="question_agent",
    model="gemini-2.5-pro",  # Or another supported model
    description="you create question based on RAG searching",
    instruction="**ROLE**\n" \
                "You are an agent responsible to create a question and evaluate the answer. \n" \
                "Your role is to create a specific question based on documents retrieved by 'retrieve_context' tool, analyze the user reply and provide a score. \n" \
                "**INTERACTION**.\n"\
                "- ask the user the topic which it's interested to if not provided\n" \
                "- always call tool 'retrieve_context' for retrieve information. \n" \
                "- create a single question only based on the corpus. " \
                "  You are not allowed to create question based on your internal knowledge. " \
                "  After creating the question you need to translate your question in Italian language. \n" \
                "- analyze the user reply, compare to the information retrieved and grade it with a score from 1 to 5. provide the user a clear reply only with the score",
    tools = [retrieve_context_tool],
    before_tool_callback=before_tool_callback,  
    after_tool_callback=after_tool_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback 

)

question_agent_tool = AgentTool(question_agent)

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

    runner = Runner(agent=question_agent, session_service=session_service, app_name=APP_NAME)

    current_session_id = str(uuid.uuid4())

    async def fetch_data(current_session_id, initial_state):
        session = await session_service.create_session( app_name=APP_NAME, user_id="0", session_id=current_session_id, state=initial_state)
        return session

    session = asyncio.run(fetch_data(current_session_id, initial_state))    

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

