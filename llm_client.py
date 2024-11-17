from openai import OpenAI, OpenAIError
import os
from dotenv import load_dotenv
from helpers import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows, get_recently_played_tracks, search_artist, get_artist_info, search_item
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
            {"role": "user", "content": "Tell me about album."},
            {"role": "assistant", "content": "album_info"},
            {"role": "user", "content": "Search playlist."},
            {"role": "assistant", "content": "playlist_info"},
            {"role": "user", "content": "What have I listened to recently?"},
            {"role": "assistant", "content": "recent_tracks"},
            {"role": "user", "content": "Recommend me some podcasts."},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "What audiobooks do I have saved?"},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "List my saved shows."},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "Recommend me some songs by Taylor Swift for a workout."},  # Example recommendation query
            {"role": "assistant", "content": "recommendation"},
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
    

    def fetch_general_info(self, entity_type, entity_name, query):  # Add query parameter
        messages = [
            {"role": "system", "content": "You are a music knowledge assistant. Answer questions directly. If the question is about streaming, popularity, genres, or current stats, use the Spotify data provided. For historical or biographical questions, provide relevant facts only."},
            {"role": "user", "content": f"Question: {query}\n\nProvide a direct answer focusing only on what was asked."}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            print(f"Error fetching general info: {e}")
            return None
    
    def process_query(self, query, spotify_data, access_token, session_id):
        query_type = self.classify_query(query)

        if session_id not in self.memory:
            self.memory[session_id] = {"history": []}

        # Append new query to session history
        self.memory[session_id]["history"].append({"query": query})

        try:
            # If the query type is 'recommend', use the parse_user_input function
            if query_type == 'recommend':
                extracted_info = self.parse_user_input(query)
                detailed_prompt = (
                    f"The user is asking for a recommendation. Based on the extracted information: {extracted_info}, generate appropriate recommendations."
                )
            elif query_type == 'top_artists':
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
                podcasts, audiobooks = [], []

                if 'items' in data:
                    for item in data['items']:
                        show = item.get('show', {})
                        show_type = self.classify_show(show)
                        if show_type == "podcast":
                            podcasts.append(show.get('name', 'Unknown Show'))
                        elif show_type == "audiobook":
                            audiobooks.append(show.get('name', 'Unknown Show'))

                if not podcasts and not audiobooks:
                    detailed_prompt = (
                        "Based on your Spotify data, it appears that you haven't saved any podcasts or audiobooks yet. To save a show, just click on the 'Heart' icon next to the show name."
                    )
                else:
                    detailed_prompt = (
                        f"Podcasts:\n{podcasts}\nAudiobooks:\n{audiobooks}\nUser Query: {query}\nResponse:"
                    )
            elif query_type == 'recent_tracks':
                data = get_recently_played_tracks(access_token)
                detailed_prompt = (
                    "The user wants to know their recently played tracks. Provide a list of recently played tracks based on the provided Spotify data.\n"
                    f"Here is the user's Spotify data:\n{data}\nUser Query: {query}\nResponse:"
                )
            # Handle each query type individually
            elif query_type == 'artist_info':
                # Extract artist name from query
                artist_name = query.split()[-1]  # Simple extraction for now
                artist_info = search_artist(artist_name, access_token)
                
                # Pass the full query to get contextual response
                response = ""
                
                # If query is about stats/genres/followers, include Spotify data
                if any(word in query.lower() for word in ['followers', 'popular', 'genre', 'streams']):
                    response += f"Spotify Statistics for {artist_name}:\n"
                    response += f"Genres: {', '.join(artist_info['genres'])}\n"
                    response += f"Followers: {artist_info['followers']}\n"
                    response += f"Popularity: {artist_info['popularity']}/100\n"
                
                # Get general info with the specific question
                general_info = self.fetch_general_info("artist", artist_name, query)
                if general_info:
                    response += general_info
                    
                return response

            elif query_type == 'album_info':
                album_name = query.split("album")[-1].strip()
                album_info = search_item(album_name, 'album', access_token)
                general_info = self.fetch_general_info("album", album_name)  # Fetch general info

                if album_info:
                    detailed_prompt = (
                        f"Here is detailed information about {album_name} from Spotify:\n"
                        f"Release Date: {album_info['release_date']}\n"
                        f"Total Tracks: {album_info['total_tracks']}\n"
                        f"Album Type: {album_info['album_type']}\n"
                        f"URL: {album_info['url']}\n"
                        f"\nGeneral Information: {general_info}"
                    )
                else:
                    detailed_prompt = f"Sorry, I couldn't find any information about the album '{album_name}' on Spotify.\n"
                    if general_info:
                        detailed_prompt += f"\nBut here is some general information:\n{general_info}"

            elif query_type == 'playlist_info':
                playlist_name = query.split("playlist")[-1].strip()
                playlist_info = search_item(playlist_name, 'playlist', access_token)
                general_info = self.fetch_general_info("playlist", playlist_name)  # Fetch general info

                if playlist_info:
                    detailed_prompt = (
                        f"Here is detailed information about the playlist '{playlist_name}' from Spotify:\n"
                        f"Description: {playlist_info['description']}\n"
                        f"Number of Tracks: {playlist_info['total_tracks']}\n"
                        f"Collaborative: {playlist_info['collaborative']}\n"
                        f"Owner: {playlist_info['owner']}\n"
                        f"URL: {playlist_info['url']}\n"
                        f"\nGeneral Information: {general_info}"
                    )
                else:
                    detailed_prompt = f"Sorry, I couldn't find any information about the playlist '{playlist_name}' on Spotify.\n"
                    if general_info:
                        detailed_prompt += f"\nBut here is some general information:\n{general_info}"

            else:
                data = spotify_data
                detailed_prompt = f"Sorry, I couldn't classify your query '{query}'. Could you clarify?"

            # Create the messages for the OpenAI API call
            messages = [
                {"role": "system", "content": "You are a personal Spotify assistant. Based on the user's query and their Spotify data, provide a helpful and accurate response."},
                {"role": "user", "content": detailed_prompt}
            ]

            print("Messages Sent to OpenAI API:", messages)  # Log messages

            # Send the prompt to OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=400  # Increase max tokens to ensure a complete response
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
        


    # Parse user input to identify artist, genre, or mood
    def parse_user_input(self, query):
        messages = [
            {"role": "system", "content": "You are a music assistant. Analyze the user's query and extract relevant information such as artist names, genres, or mood-related traits."},
            {"role": "user", "content": query}
        ]
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=100
            )
            extracted_info = response.choices[0].message.content.strip()
            print(f"Extracted Info: {extracted_info}")
            return extracted_info
        except OpenAIError as e:
            print(f"Error parsing user input with LLM: {e}")
            return "Error extracting information."
    
class SpotifyClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def classify_show(self, show):
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
        
    def search_for_artist(self, artist_name):
        # Call the imported search_artist function from helpers
        return search_artist(artist_name, self.access_token)
    
    def get_recommendations(self, artist_id=None, seed_genres=None, min_danceability=None, max_danceability=None, min_energy=None, max_energy=None, target_danceability=None, target_energy=None):
        """
        Fetch recommendations from the Spotify API based on artist ID, genres, and tunable parameters.
        """
        endpoint = "https://api.spotify.com/v1/recommendations"
        params = {
            "limit": 10,  # Example limit
            "seed_artists": artist_id if artist_id else None,
            "seed_genres": seed_genres if seed_genres else None,
            "min_danceability": min_danceability,
            "max_danceability": max_danceability,
            "target_danceability": target_danceability,
            "min_energy": min_energy,
            "max_energy": max_energy,
            "target_energy": target_energy
        }
        
        # Remove keys with None values to avoid sending them in the request
        params = {k: v for k, v in params.items() if v is not None}

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        # Make the request to Spotify's API
        response = requests.get(endpoint, headers=headers, params=params)

        if response.status_code == 200:
            recommendations = response.json()
            return recommendations['tracks']  # Returns the recommended tracks
        else:
            return f"Error fetching recommendations: {response.status_code}"
     
    

