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
            {"role": "user", "content": "Recommend me some podcasts."},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "What audiobooks do I have saved?"},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "List my saved shows."},
            {"role": "assistant", "content": "saved_shows"},
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
    def classify_show(show):
        """
        Classify the type of show based on its metadata.
        """
        description = show.get("description", "").lower()
        publisher = show.get("publisher", "").lower()

        audiobook_keywords = ["audiobook", "narrator", "narrated by", "read by", "author"]
        is_audiobook = any(keyword in description for keyword in audiobook_keywords)

        print(f"Show: {show.get('name', 'Unknown Show')}, Description: {description}, Publisher: {publisher}, Is Audiobook: {is_audiobook}")

        if is_audiobook:
            return "audiobook"
        else:
            return "podcast"
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
                print(f"Saved Shows Data: {data}")
                podcasts = []
                audiobooks = []

                if 'items' in data:
                    for item in data['items']:
                        show = item.get('show', {})
                        print(f"Processing show: {show}")
                        show_type = self.classify_show(show)
                        if show_type == "podcast":
                            podcasts.append(show.get('name', 'Unknown Show'))
                        elif show_type == "audiobook":
                            audiobooks.append(show.get('name', 'Unknown Show'))
                
                print(f"Podcasts: {podcasts}")
                print(f"Audiobooks: {audiobooks}")

                if not podcasts and not audiobooks:
                    detailed_prompt = (
                        "Based on your Spotify data, it appears that you haven't saved any podcasts or audiobooks yet. To save a show, just click on the 'Heart' icon next to the show name."
                    )
                else:
                    detailed_prompt = (
                        "The user wants to know their saved shows. Provide a list of saved podcasts and audiobooks based on the provided Spotify data.\n"
                        f"Podcasts:\n{podcasts}\nAudiobooks:\n{audiobooks}\nUser Query: {query}\nResponse:"
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
            else:
                data = spotify_data
                detailed_prompt = (
                    "Based on the user's Spotify data, provide relevant information.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )

            if 'recommend song' in query.lower():
                detailed_prompt = (
                    "The user wants new song recommendations. Use the provided Spotify data to understand the user's preferences, "
                    "and also reference broader music knowledge to suggest new songs and artists that the user might like but hasn't listened to yet. "
                    "Here is the user's Spotify data:\n"
                    f"{data}\nUser Query: {query}\nResponse:"
                )
            if 'recommend shows' in query.lower():
                detailed_prompt = (
                    "The user wants new show recommendations. Use the provided Spotify data to understand the user's preferences, "
                    "and also reference broader knowledge to suggest new shows and podcasts that the user might like but hasn't listened to yet. "
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
            response_text = response.choices[0].message.content.strip()
            
            # Append the response to session history
            self.memory[session_id]["history"].append({"response": response_text})
            return response_text
            
        except OpenAIError as e:
            print(f"Error processing query with LLM: {e}")
            return "Sorry, I couldn't process your request at this time."
        except Exception as e:
            print(f"Unexpected error in process_query: {e}")
            return "An unexpected error occurred."