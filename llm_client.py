from openai import OpenAI
from typing import Dict, Iterator, List, Optional
import json
from dotenv import load_dotenv
import os
from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler

from logger_config import setup_logger
logger = setup_logger(__name__)


class LLMClient:
    def __init__(self, model: str = "gpt-4o"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}
        logger.info(f"Initialized LLMClient with model: {model}")
        
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        try:
            logger.info(f"Processing query for session {session_id[:8]}...")
            
            if session_id not in self.chat_history:
                self.chat_history[session_id] = []
                
            messages = [
                {"role": "system", "content": "You are a Spotify assistant. Use available tools to fetch real-time music data when needed."}
            ]
            messages.extend(self.chat_history[session_id][-5:])
            messages.append({"role": "user", "content": query})
            
            # First check if we need to use tools
            logger.debug("Making initial API call to OpenAI")
            first_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=SPOTIFY_TOOLS,
                tool_choice="auto"
            )

            assistant_message = first_response.choices[0].message
            
            response = ""
            
            # If tools are needed, handle them first
            if assistant_message.tool_calls:
                function_handler = SpotifyFunctionHandler(access_token)
                for tool_call in assistant_message.tool_calls:
                    result = function_handler.execute_function(tool_call)
                    if result is None:
                        logger.warning("No data found for tool call")
                        result = {"error": "No data found"}
                    
                    messages.extend([
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{"id": tool_call.id, "type": "function", "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments}}]
                        },
                        {
                            "role": "tool",
                            "content": json.dumps(result),
                            "tool_call_id": tool_call.id
                        }
                    ])

            logger.debug("Making final API call to OpenAI with tool results")
            # Now stream the final response (whether tools were used or not)
            stream_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    response += content
                    yield content
            
            # Update chat history only once at the end
            if response:
                logger.debug("Updating chat history with assistant's response")
                self.chat_history[session_id].append({"role": "assistant", "content": response})
                
        except Exception as e:
            logger.exception("Error in processing query")
            yield f"Error: {str(e)}"