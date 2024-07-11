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
                detailed_prompt = (
                    "The user wants to know their top artists. Provide a list of the top artists based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{spotify_data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'top_tracks':
                detailed_prompt = (
                    "The user wants to know their top tracks. Provide a list of the top tracks based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{spotify_data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'followed_artists':
                data = get_followed_artists(access_token)
                detailed_prompt = (
                    "The user wants to know the artists they follow. Provide a list of followed artists based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'playlists':
                data = get_user_playlists(access_token)
                detailed_prompt = (
                    "The user wants to know their playlists. Provide a list of playlists based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'saved_shows':
                data = get_saved_shows(access_token)
                detailed_prompt = (
                    "The user wants to know their saved shows. Provide a list of saved shows based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'recent_tracks':
                data = get_recently_played_tracks(access_token)
                detailed_prompt = (
                    "The user wants to know their recently played tracks. Provide a list of recently played tracks based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )
            elif query_type == 'artist_info':
                detailed_prompt = (
                    "The user wants to know about a specific artist. Use your broader music knowledge to provide detailed information about the artist mentioned in the query.\n"
                    f"User Query: {query}\nResponse:"
                )
            else:
                data = spotify_data
                detailed_prompt = (
                    "Based on the user's Spotify data, provide relevant information.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )

            if 'recommend' in query.lower():
                detailed_prompt = (
                    "The user wants new song recommendations. Use the provided Spotify data to understand the user's preferences, "
                    "and also reference broader music knowledge to suggest new songs and artists that the user might like but hasn't listened to yet. "
                    "Here is the user's Spotify data:\n"
                    f"{data}\nUser Query: {query}\nResponse:"
                )

            messages = [
                {"role": "system", "content": "You are a personal Spotify assistant. Based on the user's query and their Spotify data, provide a helpful and accurate response."},
                {"role": "user", "content": detailed_prompt}
            ]
            print("Messages Sent to OpenAI API:", messages)  # Log messages

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=400  # Increase the max tokens value to ensure the complete response
            )
            print("Response from OpenAI API:", response)  # Log response
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print(f"Error processing query with LLM: {e}")
            return "Sorry, I couldn't process your request at this time."
        except Exception as e:
            print(f"Unexpected error in process_query: {e}")
            return "An unexpected error occurred."

