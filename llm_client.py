from openai import OpenAI
from typing import Dict, Iterator, List
import json
from dotenv import load_dotenv
import os
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import workflow, task
from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler
from logger_config import setup_logger

logger = setup_logger(__name__)

class LLMClient:
    def __init__(self, model: str = "gpt-4"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}

        Traceloop.init(
            disable_batch=True,
            api_key=os.getenv('TRACELOOP_API_KEY_PROD'),
            resource_attributes={"env": "prod", "version": "1.0.0"}
        )

        logger.info(f"Initialized LLMClient with model: {model}")

    @workflow(name="process_query_workflow")
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        logger.info(f"Processing query for session {session_id[:8]}...")

        if session_id not in self.chat_history:
            self.chat_history[session_id] = []

        # Construct messages
        messages = self._build_messages(session_id, query)

        # Initial OpenAI API call
        assistant_message = self._initial_openai_call(messages)

        # Handle tool calls
        if assistant_message.tool_calls:
            messages = self._handle_tool_calls(assistant_message.tool_calls, access_token, messages)

        # Final OpenAI API call with streaming
        response = ""
        for chunk in self._final_openai_call(messages):
            response += chunk
            yield chunk

        # Update chat history
        if response:
            self.chat_history[session_id].append({"role": "assistant", "content": response})

    @task(name="build_messages")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        messages = [
            {"role": "system", "content": "You are a Spotify assistant. Use available tools to fetch real-time music data when needed."}
        ]
        messages.extend(self.chat_history[session_id][-5:])
        messages.append({"role": "user", "content": query})
        logger.info(f"Built messages for session {session_id[:8]}")
        return messages

    @task(name="initial_openai_call")
    def _initial_openai_call(self, messages: List[Dict[str, str]]) -> Dict:
        logger.info("Making initial OpenAI API call")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=SPOTIFY_TOOLS,
            tool_choice="auto"
        )
        return response.choices[0].message

    @task(name="handle_tool_calls")
    def _handle_tool_calls(self, tool_calls: List[Dict], access_token: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        logger.info("Handling tool calls")
        function_handler = SpotifyFunctionHandler(access_token)
        
        for tool_call in tool_calls:
            result = function_handler.execute_function(tool_call)
            if result is None:
                logger.warning("No data found for tool call")
                result = {"error": "No data found"}
                
            messages.extend([
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                },
                {
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                }
            ])
        
        return messages

    @task(name="final_openai_call")
    def _final_openai_call(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        logger.info("Making final OpenAI API call")
        stream_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )

        for chunk in stream_response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content