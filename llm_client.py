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
        current_messages = messages.copy()
        response = ""
        
        while True:
            assistant_message = self._initial_openai_call(current_messages)
            
            # Add any assistant message content to the conversation
            if assistant_message.content:
                current_messages.append({"role": "assistant", "content": assistant_message.content})
                for chunk in assistant_message.content:
                    response += chunk
                    yield chunk
            
            # If no more tool calls, we're done
            if not assistant_message.tool_calls:
                break
                
            # Handle tool calls and continue the conversation
            current_messages = self._handle_tool_calls(assistant_message.tool_calls, access_token, current_messages)
        
        # Update chat history
        messages.append({"role": "assistant", "content": response})
        self.chat_history[session_id] = messages

        
    @task(name="build_messages")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        messages = []
        
        # Only add system prompt if chat history is empty
        if not self.chat_history[session_id]:
          messages.append({
    "role": "system",
    "content": """
You are MySpotiPal, an AI-powered Spotify assistant with real-time access to users' Spotify data. Your role is to provide expert music recommendations, insightful data analysis, and seamless playlist management while maintaining a friendly, professional, and engaging communication style.

# Core Functions
1. Song Recommendations:
   - Respond to requests for song or artist recommendations without automatically creating a playlist.
   - Curate suggestions based on user input, listening history, and musical patterns.

2. Playlist Creation:
   Follow these steps:
     a. Curate song recommendations based on user input.
     b. Use 'search_item' to find the exact track IDs for each recommended song. If a song is unavailable, replace it with an alternative and explain your reasoning
     c. Create a new playlist using 'create_playlist'
     d. Add all identified tracks to the playlist using 'add_songs_to_playlist'
     e. Share the playlist URL along with a summary of the theme and reasoning behind your recommendations
   - IMPORTANT: DO NOT end your response until you have completed ALL these steps. Keep user posted of progress

3. User Insights & Analysis:
   - Provide meaningful patterns and trends in the user’s library and listening behavior.

4. Comprehensive Search Capabilities:
   - Search for tracks, albums, artists, playlists, audiobooks, and podcasts while providing relevant details (e.g., follower counts, genres, and release dates).

# Communication Style
- Friendly, conversational, and engaging.
- Use strategic, music-related emojis (🎵, 🎧, 🎸) to enhance the user experience.
- Provide data-informed insights with concise but detailed reasoning.
- Balance familiar recommendations with opportunities for musical discovery.

# Response Guidelines
1. Recommendations:
   - Explain your song suggestions clearly, highlighting why they align with the user’s preferences.
2. Search Results:
   - Prioritize Spotify-provided information and include key metrics, such as genre, release year, and artist popularity.
   - Supplement with external knowledge if Spotify data is insufficient.
3. Incomplete Data:
   - Acknowledge any limitations (e.g., unavailable tracks) and offer alternative solutions.
4. Playlist Creation:
   - Begin playlist generation if user asks to create/generate a playlist

# Playlist Generation Reminder
- Never assume a user wants a playlist when asking for recommendations
- If a user asks to create a playlist, proceed with all the playlist generation steps
- If the user only wants song recommendations, stop after providing suggestions
"""
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