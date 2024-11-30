from openai import OpenAI
from typing import Dict, Iterator, List, Optional
import logging
from logging.handlers import RotatingFileHandler
import json
from dotenv import load_dotenv
import os

from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler

# Configure logging
logger = logging.getLogger('llm_client')
logger.setLevel(logging.DEBUG)
# Prevent propagation to parent loggers
logger.propagate = False  

# Create log directory if it doesn't exist
os.makedirs('/var/log/myspotipal', exist_ok=True)

# Create file handler for logging to file
file_handler = RotatingFileHandler(
    '/var/log/myspotipal/llm.log',
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] in %(module)s: %(message)s'
))

# Create console handler for logging to stdout
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] in %(module)s: %(message)s'
))

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class LLMClient:
    def __init__(self, model: str = "gpt-4o"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}
        logger.info(f"Initialized LLMClient with model: {model}")
        
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        try:
            logger.info(f"Processing query for session {session_id[:8]}...")  # Log only first 8 chars of session ID
            
            if session_id not in self.chat_history:
                logger.debug(f"Initializing new chat history for session {session_id[:8]}")
                self.chat_history[session_id] = []
                
            messages = [
                {"role": "system", "content": "You are a Spotify assistant. Use available tools to fetch real-time music data when needed."}
            ]
            for msg in self.chat_history[session_id][-5:]:
                messages.append(msg)
            messages.append({"role": "user", "content": query})
            
            function_handler = SpotifyFunctionHandler(access_token)
            response = ""
            
            logger.debug("Making initial API call to OpenAI")
            first_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=SPOTIFY_TOOLS,
                tool_choice="auto"
            )

            assistant_message = first_response.choices[0].message
            if assistant_message.tool_calls:
                logger.info(f"Received {len(assistant_message.tool_calls)} tool calls")
                for tool_call in assistant_message.tool_calls:
                    logger.debug(f"Executing tool call: {tool_call.function.name}")
                    result = function_handler.execute_function(tool_call)
                    
                    if result is None:
                        logger.warning("No data found for tool call")
                        result = {"error": "No data found"}
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": tool_call.id, "type": "function", "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments}}]
                    })
                    
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                
                logger.debug("Making final API call to OpenAI with tool results")
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                for chunk in final_response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        response += content
                        yield content
                        
            else:
                logger.debug("No tool calls needed, streaming direct response")
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
            
            if response:
                logger.debug("Updating chat history with assistant's response")
                self.chat_history[session_id].append({"role": "assistant", "content": response})
                
        except Exception as e:
            logger.exception("Error in processing query")
            yield f"Error: {str(e)}"