from openai import OpenAI
from typing import Dict, Iterator, List
import json
from dotenv import load_dotenv
import os
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import workflow, task
from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler
from logger_config import setup_logger
from system_prompt import SYSTEM_PROMPT

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
    def process_query(
        self,
        query: str,          # The user's input query
        spotify_data: Dict,  # Dictionary containing Spotify-related data
        access_token: str,   # Spotify API access token
        session_id: str      # Unique identifier for the chat session
    ) -> Iterator[str]:      # Returns a string iterator for streaming responses
        """
        Process a user query, handling both direct responses and tool calls with Spotify API.
        Streams responses back to the user and maintains chat history.

        Args:
            query: User's input text query
            spotify_data: Dictionary containing relevant Spotify data
            access_token: Valid Spotify API access token
            session_id: Unique identifier for the chat session

        Yields:
            Encoded string chunks of the assistant's response

        Note:
            - Maintains chat history per session
            - Handles streaming responses from OpenAI
            - Processes tool calls for Spotify API interactions
        """
        logger.info(f"Processing query for session {session_id[:8]}...")
        
        # Initialize chat history for new sessions
        if session_id not in self.chat_history:
            self.chat_history[session_id] = []
            logger.warning(f"Chat history not found for session {session_id[:8]}. Creating new chat history.")
        
        # Build message context including history
        messages = self._build_messages(session_id, query)
        logger.info(f"Length of messages: {len(messages)}")      
        
        current_messages = messages.copy()  # Working copy of messages
        response = ""  # Accumulator for complete response
        
        while True:
            # Get streaming response from OpenAI
            assistant_message = self._initial_openai_call(current_messages)
            tool_calls = []  # Accumulator for tool calls in this response

            # Process each chunk of the streaming response
            for chunk in assistant_message:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    # Handle text content
                    response += delta.content
                    yield delta.content.encode('utf-8')
                elif delta and delta.tool_calls:
                    # Handle tool calls (e.g., Spotify API functions)
                    tcchunklist = delta.tool_calls
                    for tcchunk in tcchunklist:
                        # Initialize new tool call structure if needed
                        if len(tool_calls) <= tcchunk.index:
                            tool_calls.append({
                                "id": "", 
                                "type": "function", 
                                "function": { 
                                    "name": "", 
                                    "arguments": "" 
                                }
                            })
                        tc = tool_calls[tcchunk.index]

                        # Accumulate tool call information from chunks
                        if tcchunk.id:
                            tc["id"] += tcchunk.id
                        if tcchunk.function.name:
                            tc["function"]["name"] += tcchunk.function.name
                        if tcchunk.function.arguments:
                            tc["function"]["arguments"] += tcchunk.function.arguments

            # Exit loop if no tool calls were made
            if not tool_calls:
                break
                
            # Convert accumulated tool calls to format needed by handler
            formatted_tool_calls = [
                type('ToolCall', (), {
                    'id': tc['id'],
                    'function': type('Function', (), {
                        'name': tc['function']['name'],
                        'arguments': tc['function']['arguments']
                    })
                }) for tc in tool_calls
            ]
            
            # Process tool calls and update conversation context
            current_messages = self._handle_tool_calls(formatted_tool_calls, access_token, current_messages)
        
        # Update chat history with final response
        messages.append({"role": "assistant", "content": response})
        self.chat_history[session_id] = messages
        
    @task(name="build_messages")
    def _build_messages(self, session_id: str, query: str) -> List[Dict[str, str]]:
        messages = []
        
        # Only add system prompt if chat history is empty
        if not self.chat_history[session_id]:
          messages.append({
    "role": "system",
    "content": SYSTEM_PROMPT
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
            stream=True
        )
        return response
    

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