from openai import OpenAI
from typing import Dict, Iterator, List, Optional
import logging
import json
from dotenv import load_dotenv
import os

from ai_tools import SPOTIFY_TOOLS, SpotifyFunctionHandler


class LLMClient:
    def __init__(self, model: str = "gpt-4o"):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = model
        self.chat_history: Dict[str, List[Dict[str, str]]] = {}
        logging.basicConfig(level=logging.INFO)
        
    def process_query(self, query: str, spotify_data: Dict, access_token: str, session_id: str) -> Iterator[str]:
        try:
            if session_id not in self.chat_history:
                self.chat_history[session_id] = []
                
            messages = [
                {"role": "system", "content": "You are a Spotify assistant. Use available tools to fetch real-time music data when needed."}
            ]
            for msg in self.chat_history[session_id][-5:]:
                messages.append(msg)
            messages.append({"role": "user", "content": query})
            
            function_handler = SpotifyFunctionHandler(access_token)
            response = ""
            
            first_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=SPOTIFY_TOOLS,
                tool_choice="auto"
            )

            assistant_message = first_response.choices[0].message
            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    result = function_handler.execute_function(tool_call)
                    result = result if result is not None else {"error": "No data found"}
                        
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
                self.chat_history[session_id].append({"role": "assistant", "content": response})
                
        except Exception as e:
            logging.exception("Error in processing")
            yield f"Error: {str(e)}"