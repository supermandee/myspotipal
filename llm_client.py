from openai import OpenAI, OpenAIError
import os
from dotenv import load_dotenv

class LLMClient:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )

    def process_query(self, query, spotify_data):
        messages = [
            {"role": "system", "content": "You are a personal Spotify assistant. Based on the user's query and their Spotify data, provide a helpful and accurate response."},
            {"role": "user", "content": f"User Query: {query}\nSpotify Data: {spotify_data}\nResponse:"}
        ]
        print("Messages Sent to OpenAI API:", messages)  # Log messages

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # Use the latest model name
                messages=messages,
                max_tokens=150
            )
            print("Response from OpenAI API:", response)  # Log response
            return response.choices[0].message.content.strip()
        except OpenAIError as e:  # Updated error handling
            print(f"Error processing query with LLM: {e}")
            return "Sorry, I couldn't process your request at this time."