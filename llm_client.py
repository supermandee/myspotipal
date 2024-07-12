from openai import OpenAI, OpenAIError
import os
from dotenv import load_dotenv
from helpers import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows, get_recently_played_tracks, search_artist, get_artist_info
import uuid

class LLMClient:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.memory = {}  # Simple in-memory storage for session
        self.access_token = os.getenv('SPOTIFY_ACCESS_TOKEN')

    def generate_session_id(self):
        return str(uuid.uuid4())

    def classify_query(self, query):
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Classify the following query into one of the categories: top_artists, top_tracks, followed_artists, playlists, saved_shows, recent_tracks, artist_info, or unknown. Respond with only the category."},
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
            {"role": "user", "content": "Tell me about Modern Sophia."},
            {"role": "assistant", "content": "artist_info"},
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

    def process_query(self, query, spotify_data, access_token, session_id):
        query_type = self.classify_query(query)

        if session_id not in self.memory:
            self.memory[session_id] = {"history": []}

        # Append new query to session history
        self.memory[session_id]["history"].append({"query": query})
        
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
                artist_name = query.split("about")[-1].strip()
                artist_info = search_artist(artist_name, access_token)
                if artist_info:
                    detailed_prompt = (
                        "The user wants to know about an artist. Provide detailed information about the artist.\n"
                        f"Here is the information about {artist_name}:\n{artist_info}\nUser Query: {query}\nResponse:"
                    )
                else:
                    detailed_prompt = (
                        "The user wants to know about an artist, but the information is not available in the Spotify data. Use general knowledge to provide information about the artist.\n"
                        f"User Query: {query}\nResponse:"
                    )
            elif query_type == 'album_info':
                album_name = query.split("about")[-1].strip()
                album_info = search_album(album_name, access_token)
                if album_info:
                    detailed_prompt = (
                        "The user wants to know about an album. Provide detailed information about the album.\n"
                        f"Here is the information about {album_name}:\n{album_info}\nUser Query: {query}\nResponse:"
                    )
                else:
                    detailed_prompt = (
                        "The user wants to know about an album, but the information is not available in the Spotify data. Use general knowledge to provide information about the album.\n"
                        f"User Query: {query}\nResponse:"
                    )
            elif query_type == 'show_info':
                show_name = query.split("about")[-1].strip()
                show_info = search_show(show_name, access_token)
                if show_info:
                    detailed_prompt = (
                        "The user wants to know about a show. Provide detailed information about the show.\n"
                        f"Here is the information about {show_name}:\n{show_info}\nUser Query: {query}\nResponse:"
                    )
                else:
                    detailed_prompt = (
                        "The user wants to know about a show, but the information is not available in the Spotify data. Use general knowledge to provide information about the show.\n"
                        f"User Query: {query}\nResponse:"
                    )
            elif query_type == 'podcast_info':
                podcast_name = query.split("about")[-1].strip()
                podcast_info = search_podcast(podcast_name, access_token)
                if podcast_info:
                    detailed_prompt = (
                        "The user wants to know about a podcast. Provide detailed information about the podcast.\n"
                        f"Here is the information about {podcast_name}:\n{podcast_info}\nUser Query: {query}\nResponse:"
                    )
                else:
                    detailed_prompt = (
                        "The user wants to know about a podcast, but the information is not available in the Spotify data. Use general knowledge to provide information about the podcast.\n"
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
 
             # Append the response to session history
            self.memory[session_id]["history"].append({"response": response_text})
            return response_text
        
        except OpenAIError as e:
            print(f"Error processing query with LLM: {e}")
            return "Sorry, I couldn't process your request at this time."
        except Exception as e:
            print(f"Unexpected error in process_query: {e}")
            return "An unexpected error occurred."
