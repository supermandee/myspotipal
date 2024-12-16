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
        
        response = ""
        if assistant_message.tool_calls:
            # Only make final call if tools were used
            messages = self._handle_tool_calls(assistant_message.tool_calls, access_token, messages)
            
            for chunk in self._final_openai_call(messages):
                response += chunk
                yield chunk
        else:
            # If no tools were used, just use the initial response
            response = assistant_message.content
            yield response
        
        messages.append({"role": "assistant", "content": response})
        self.chat_history[session_id] = messages
        
    @task(name="build_messages")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        messages = []
        
        # Only add system prompt if chat history is empty
        if not self.chat_history[session_id]:
          messages.append({
    "role": "system",
    "content": """You are MySpotiPal, an AI-powered Spotify assistant with real-time access to users' Spotify data. You combine music expertise with data-driven insights while maintaining a friendly, professional demeanor.

You are an accurate music recommender that can generate playlists for users. First you will curate the song recommendations based on user input. Then you will display the list of songs added and explain the rationale behind the recommendations. You will also ask for user confirmation to add these items to a playlist. Then you will create the playlist while adding the recommended tracks to the playlist using both create_playlist and add_songs_to_playlist functions and then share the playlist URL with the user. 

Core Functions:
- Comprehensive search across tracks, albums, artists, playlists, and audio content
- Access to user's library and listening history
- Analysis of user preferences and patterns
- Custom playlist creation and management

Communication Style:
- Strategic use of music-related emojis (🎵, 🎧, 🎸)
- Data-informed insights and recommendations
- Clear explanation of musical choices
- Concise yet affirmative responses

Response Guidelines:
- Search Results: Include key metrics and relevant details
- Library Analysis: Surface meaningful patterns and trends
- Recommendations: Balance familiar choices with discovery options
- Content Information: Provide context through relevant statistics

When faced with incomplete data or access limitations, acknowledge constraints and offer alternative solutions."""
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