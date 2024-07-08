from openai import OpenAI, OpenAIError
import os
from dotenv import load_dotenv
from helpers import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows, get_recently_played_tracks

class LLMClient:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )

    def classify_query(self, query):
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Classify the following query into one of the categories: top_artists, top_tracks, followed_artists, playlists, saved_shows, recent_tracks, or unknown. Respond with only the category."},
            {"role": "user", "content": "What are my favorite artists?"},
            {"role": "assistant", "content": "top_artists"},
            {"role": "user", "content": "Show me my top songs."},
            {"role": "assistant", "content": "top_tracks"},
            {"role": "user", "content": "Who do I follow?"},
            {"role": "assistant", "content": "followed_artists"},
            {"role": "user", "content": "List my playlists."},
            {"role": "assistant", "content": "playlists"},
            {"role": "user", "content": "What podcasts do I have saved?"},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "What have I listened to recently?"},
            {"role": "assistant", "content": "recent_tracks"},
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=10
            )
            classification = response.choices[0].message.content.strip()
            print(f"Classified Query: {classification}")  # Log the classification
            return classification
        except OpenAIError as e:
            print(f"Error classifying query with LLM: {e}")
            return "unknown"
        except Exception as e:
            print(f"Unexpected error in classify_query: {e}")
            return "unknown"

    def process_query(self, query, spotify_data, access_token):
        query_type = self.classify_query(query)
        
        try:
            if query_type == 'top_artists':
                data = get_top_items(access_token, 'short_term', 'artists')
            elif query_type == 'top_tracks':
                data = get_top_items(access_token, 'short_term', 'tracks')
            elif query_type == 'followed_artists':
                data = get_followed_artists(access_token)
            elif query_type == 'playlists':
                data = get_user_playlists(access_token)
            elif query_type == 'saved_shows':
                data = get_saved_shows(access_token)
            elif query_type == 'recent_tracks':
                data = get_recently_played_tracks(access_token)
            else:
                data = spotify_data  # Default to cached data if no specific query is matched

            messages = [
                {"role": "system", "content": "You are a personal Spotify assistant. Based on the user's query and their Spotify data, provide a helpful and accurate response."},
                {"role": "user", "content": f"User Query: {query}\nSpotify Data: {data}\nResponse:"}
            ]
            print("Messages Sent to OpenAI API:", messages)  # Log messages

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=150
            )
            print("Response from OpenAI API:", response)  # Log response
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print(f"Error processing query with LLM: {e}")
            return "Sorry, I couldn't process your request at this time."
        except Exception as e:
            print(f"Unexpected error in process_query: {e}")
            return "An unexpected error occurred."
