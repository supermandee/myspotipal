from openai import OpenAI
from typing import Dict, Iterator, List, Optional
import json
from dotenv import load_dotenv
import os
from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import workflow, task
from logger_config import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    def __init__(self, model: str = "gpt-4o"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}

        # Initialize Traceloop
        Traceloop.init(disable_batch=True)

        logger.info(f"Initialized LLMClient with model: {model}")

    @workflow(name="process_query_workflow")
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        logger.info(f"Processing query for session {session_id[:8]}...")

        with Span(name="process_query_workflow", kind="server") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("query", query)

            # Log the span details at the beginning
            logger.info(f"Started workflow span: {span.name}", extra={"attributes": span.attributes})

        # Step 1: Build messages
        messages = self._build_messages(session_id, query)

        # Step 2: Initial OpenAI API call
        assistant_message = self._initial_openai_call(messages)

        # Step 3: Handle tool calls (if any)
        if assistant_message.tool_calls:
            self._handle_tool_calls(assistant_message.tool_calls, access_token, messages)

        # Step 4: Final OpenAI API call
        response = self._final_openai_call(messages)

        # Step 5: Update chat history
        self._update_chat_history(session_id, response)


        # Log span completion
        logger.info(
            f"Completed workflow span: {span.name}",
            extra={
                "attributes": span.attributes,
                "status": "SUCCESS",
                "start_time": span.start_time,
                "end_time": span.end_time,
            },
        )

        return response

    @task(name="build_messages_task")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        if session_id not in self.chat_history:
            self.chat_history[session_id] = []
        messages = [
            {"role": "system", "content": "You are a Spotify assistant. Use available tools to fetch real-time music data when needed."}
        ]
        messages.extend(self.chat_history[session_id][-5:])
        messages.append({"role": "user", "content": query})
        logger.info(f"Built messages for session {session_id[:8]}: {messages}")
        return messages

    @task(name="initial_openai_call_task")
    def _initial_openai_call(self, messages: List[Dict[str, str]]) -> Dict:
        logger.info("Making initial OpenAI API call.")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=SPOTIFY_TOOLS,
            tool_choice="auto"
        )
        logger.info(f"Initial OpenAI response: {response}")
        return response.choices[0].message

    @task(name="handle_tool_calls_task")
    def _handle_tool_calls(self, tool_calls: List[Dict], access_token: str, messages: List[Dict[str, str]]):
        logger.info("Handling tool calls.")
        function_handler = SpotifyFunctionHandler(access_token)
        for tool_call in tool_calls:
            result = function_handler.execute_function(tool_call)
            logger.info(f"Tool call result: {result}")
            messages.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            })

    @task(name="final_openai_call_task")
    def _final_openai_call(self, messages: List[Dict[str, str]]) -> str:
        logger.info("Making final OpenAI API call.")
        stream_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        response = ""
        for chunk in stream_response:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content
        logger.info(f"Final OpenAI response: {response}")
        return response

    def _update_chat_history(self, session_id: str, response: str):
        logger.info("Updating chat history.")
        self.chat_history[session_id].append({"role": "assistant", "content": response})