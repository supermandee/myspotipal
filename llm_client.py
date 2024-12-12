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
    @task(name="start_client")
    def __init__(self, model: str = "gpt-4o"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}

        Traceloop.init(
            disable_batch=True,
            api_key=os.getenv('TRACELOOP_API_KEY')
        )

        logger.info(f"Initialized LLMClient with model: {model}")

    @workflow(name="process_query_workflow")
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        logger.info(f"Processing query for session {session_id[:8]}...")

        if session_id not in self.chat_history:
            self.chat_history[session_id] = []
            # DEBUG: 
            logger.warning(f"Chat history not found for session {session_id[:8]}. Creating new chat history.")

        # Construct messages
        messages = self._build_messages(session_id, query)
        #DEBUG:
        logger.info(f"Lengh of messages: {len(messages)}")      

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

        messages.append({"role": "assistant", "content": response})

        self.chat_history[session_id] = messages

    @task(name="build_messages")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        messages = []
        
        # Only add system prompt if chat history is empty
        if not self.chat_history[session_id]:
          messages.append({
                    "role": "system",
                    "content": """You are MySpotiPal, an AI-powered Spotify assistant with real-time access to the user's Spotify music data. You're enthusiastic about music while maintaining professionalism and accuracy in your recommendations. Your capabilities include searching for tracks, albums, artists, playlists, shows, episodes, and audiobooks, as well as accessing the user's personal library, including saved playlists and podcasts, top songs and artists, and recently played tracks. Your interaction style should be friendly and conversational, using music-related emojis sparingly (🎵, 🎧, 🎸), showing genuine interest in users' music preferences, providing specific, data-driven insights, explaining recommendations with clear reasoning, and being concise yet informative. When responding to search queries, provide relevant details about the requested content, include popularity metrics when available, and suggest related content when appropriate. For personal library analysis, highlight interesting patterns in listening habits, provide context for statistics, and offer actionable insights. When making recommendations, base suggestions on the user's listening history, include both similar and exploratory options, and explain why each recommendation might appeal to them. For artist and track information, include relevant statistics such as followers, popularity, genres, and similar artists, along with general information. If you're unsure about any data or cannot access certain information, acknowledge this clearly and provide alternative suggestions or information that might help the user. Always prioritize accuracy over speculation."""
                })
        # Add existing chat history
        messages.extend(self.chat_history[session_id])
        
        # Add new user query and assistant response
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
        )
        return response.choices[0].message

    @task(name="handle_tool_calls")
    def _handle_tool_calls(self, tool_calls: List[Dict], access_token: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        logger.info("Handling tool calls")
        function_handler = SpotifyFunctionHandler(access_token)

        # # Create a temporary list for the current conversation
        # current_messages = messages.copy()
        
        for tool_call in tool_calls:
            result = function_handler.execute_function(tool_call)
            if result is None:
                logger.warning("No data found for tool call")
                result = {"error": "No data found"}
                
            messages.extend([
                {
                    "role": "assistant",
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