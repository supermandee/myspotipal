from openai import OpenAI, OpenAIError
import os
from dotenv import load_dotenv
from typing import Dict, Optional, List, Union
from helpers import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows, get_recently_played_tracks, search_artist, get_artist_info, search_item
import uuid
import requests
from recommendation_analyzer import RecommendationAnalyzer 

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
            {"role": "system", "content": """You are a helpful assistant. Classify the following query into one of these categories:
                top_artists, top_tracks, followed_artists, playlists, saved_shows, recent_tracks,
                artist_info, album_info, track_info, playlist_info, show_info, episode_info, audiobook_info,
                recommendation, or unknown. Respond with only the category."""},
            ## top and followed items
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
            {"role": "user", "content": "What audiobooks do I have saved?"},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "List my saved shows."},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "What have I listened to recently?"},
            {"role": "assistant", "content": "recent_tracks"},
            ## asking for info
            {"role": "user", "content": "Tell me about Modern Sophia."},
            {"role": "assistant", "content": "artist_info"},
            {"role": "user", "content": "Tell me about album."},
            {"role": "assistant", "content": "album_info"},
            {"role": "user", "content": "Search playlist."},
            {"role": "assistant", "content": "playlist_info"},
            {"role": "user", "content": "Tell me about this song Anti-Hero"},
            {"role": "assistant", "content": "track_info"},
            {"role": "user", "content": "Tell me about the show Serial"},
            {"role": "assistant", "content": "show_info"},
            {"role": "user", "content": "What's this episode of Joe Rogan about?"},
            {"role": "assistant", "content": "episode_info"},
            {"role": "user", "content": "Information about Harry Potter audiobook"},
            {"role": "assistant", "content": "audiobook_info"},
            ## recommendations
            {"role": "user", "content": "Recommend me some podcasts."},
            {"role": "assistant", "content": "saved_shows"},
            {"role": "user", "content": "Recommend me some songs by Taylor Swift for a workout."},  # Example recommendation query
            {"role": "assistant", "content": "recommendation"},
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
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
    

    def fetch_general_info(self, entity_type, entity_name, query):  
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
        
    # Update the stream_response method in your LLMClient class
    def stream_response(self, messages, max_tokens=1000):
        """
        Stream responses from OpenAI API using the provided messages.
        """
        try:
            # Use stream=True to get a streaming response
            stream = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=max_tokens,
                stream=True
            )

            # Stream each chunk
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except OpenAIError as e:
            print(f"Error streaming response: {e}")
            yield "Sorry, I couldn't process your request at this time."
        except Exception as e:
            print(f"Unexpected error during streaming: {e}")
            yield "An unexpected error occurred."
    
    def process_query(self, query, spotify_data, access_token, session_id):
            query_type = self.classify_query(query)

            if session_id not in self.memory:
                self.memory[session_id] = {"history": []}

            # Append new query to session history
            self.memory[session_id]["history"].append({"query": query})

            try:
                if query_type == 'recommendation':
                    try:
                        # Initialize the recommendation analyzer
                        analyzer = RecommendationAnalyzer()
                        
                        # Analyze the request - this will handle:
                        # - Parsing duration, mood, genres, etc.
                        # - Converting artist names to Spotify IDs
                        # - Validating and formatting all parameters
                        analysis = analyzer.analyze_request(query)
                        
                        if not analysis:
                            return iter(["I had trouble understanding your music request. Could you please rephrase it?"])
                        
                        # The analysis already contains properly formatted parameters for Spotify's API
                        # including validated audio features and resolved seed IDs
                        
                        # Get recommendations using the analyzed parameters
                        response = requests.get(
                            'https://api.spotify.com/v1/recommendations',
                            headers={'Authorization': f'Bearer {access_token}'},
                            params=analysis
                        )
                        
                        if response.status_code != 200:
                            print(f"Error from Spotify API: {response.status_code}")
                            print(f"Response: {response.text}")
                            return iter(["Sorry, I had trouble getting recommendations from Spotify."])
                            
                        tracks = response.json()['tracks']
                        
                        if not tracks:
                            return iter(["I couldn't find any recommendations matching your criteria."])
                        
                        # Format the response
                        message = "Here are some recommended songs based on your request:\n\n"
                        
                        for i, track in enumerate(tracks[:10], 1):
                            artists = ", ".join(artist['name'] for artist in track['artists'])
                            album = track['album']['name']
                            message += f"{i}. '{track['name']}' by {artists}\n"
                            message += f"   From the album: {album}\n\n"
                        
                        return iter([message])
                        
                    except Exception as e:
                        print(f"Error processing recommendation request: {e}")
                        return iter(["Sorry, I encountered an error while getting recommendations."])
                
                # Extract item name and process based on query type
                elif query_type in ['track_info', 'playlist_info', 'show_info', 'episode_info', 'audiobook_info', 'artist_info', 'album_info']:
                    messages = [
                        {"role": "system", "content": """You are a helper that identifies items in questions. 
                        For tracks, return the track name and artist in format: 'track_name by artist_name'
                        For albums, return the album name and artist in format: 'album_name by artist_name'
                        For all other items (playlists, shows, episodes, audiobooks), return just the name.
                        Return ONLY the extracted information, nothing else."""},
                        {"role": "user", "content": f"Query type: {query_type}\nQuery: {query}"}
                    ]

                    name_response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=messages,
                        max_tokens=50
                    )
                    item_name = name_response.choices[0].message.content.strip()
                    print(f"Identified item: {item_name}")

                    # Parse item_name if it contains artist information
                    search_filters = None
                    if ' by ' in item_name and query_type in ['track_info', 'album_info']:
                        name_part, artist_part = item_name.split(' by ', 1)
                        item_name = name_part.strip()
                        search_filters = {'artist': artist_part.strip()}

                    # Map query types to Spotify search types
                    search_type_mapping = {
                        'track_info': 'track',
                        'playlist_info': 'playlist',
                        'show_info': 'show',
                        'episode_info': 'episode',
                        'audiobook_info': 'audiobook',
                        'artist_info': 'artist',
                        'album_info': 'album'
                    }

                    search_type = search_type_mapping.get(query_type)
                    item_info = search_item(item_name, search_type, access_token, search_filters)
                    general_info = self.fetch_general_info(search_type, item_name, query)


                    if item_info:
                        if query_type == 'track_info':
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Song: {item_info['name']}
    - Artist(s): {', '.join(artist['name'] for artist in item_info['artists'])}
    - Album: {item_info['album']['name']}
    - Release Date: {item_info['album'].get('release_date')}
    - Popularity: {item_info.get('popularity', 'N/A')}/100
    General information: {general_info}
    """
                        elif query_type == 'playlist_info':
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Playlist: {item_info['name']}
    - Created by: {item_info['owner']['name']}
    - Total tracks: {item_info['total_tracks']}
    - Description: {item_info.get('description', 'No description available')}
    General information: {general_info}
    """
                        elif query_type == 'show_info':
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Show: {item_info['name']}
    - Publisher: {item_info['publisher']}
    - Total Episodes: {item_info['total_episodes']}
    - Description: {item_info['description']}
    General information: {general_info}
    """
                        elif query_type == 'episode_info':
                            show_info = item_info.get('show', {})
                            duration_mins = item_info['duration_ms'] // 60000
                            duration_secs = (item_info['duration_ms'] % 60000) // 1000
                            
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Episode: {item_info['name']}
    - Show: {show_info.get('name', 'N/A')}
    - Publisher: {show_info.get('publisher', 'N/A')}
    - Duration: {duration_mins}:{duration_secs:02d}
    - Release Date: {item_info.get('release_date', 'N/A')}
    - Language: {item_info.get('language', 'N/A')}
    - Description: {item_info['description']}
    General information: {general_info}
    """
                        elif query_type == 'audiobook_info':
                            detailed_prompt = f"""
Question: {query}
Spotify data:
- Audiobook: {item_info['name']}
- Author(s): {', '.join(item_info['authors'])}  # Already processed into list of names
- Narrator(s): {', '.join(item_info['narrators'])}  # Already processed into list of names
- Publisher: {item_info['publisher']}
- Chapters: {item_info['total_chapters']}
- Description: {item_info['description']}
General information: {general_info} """
                        elif query_type == 'artist_info':
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Artist: {item_info['name']}
    - Genres: {', '.join(item_info['genres'])}
    - Followers: {item_info['followers']}
    - Popularity: {item_info['popularity']}/100
    General information: {general_info}
    """
                        elif query_type == 'album_info':
                            detailed_prompt = f"""
    Question: {query}
    Spotify data:
    - Album: {item_info['name']}
    - Artist(s): {', '.join(artist['name'] for artist in item_info['artists'])}
    - Release Date: {item_info['release_date']}
    - Total Tracks: {item_info['total_tracks']}
    General information: {general_info}
    """
                    else:
                        detailed_prompt = f"Sorry, I couldn't find information about '{item_name}' on Spotify.\n"
                        if general_info:
                            detailed_prompt += f"However, here is some general information:\n{general_info}"

                    messages = [
                        {"role": "system", "content": "You are a helpful Spotify assistant. Answer the user's question naturally. Use Spotify data for current information and general information for historical or background details. Focus on answering specifically what was asked."},
                        {"role": "user", "content": detailed_prompt}
                    ]

                # Prepare the detailed prompt based on query type
                elif query_type == 'recommend':
                    extracted_info = self.parse_user_input(query)
                    detailed_prompt = f"The user is asking for a recommendation. Based on the extracted information: {extracted_info}, generate appropriate recommendations."

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

                    for show in data:
                        show_type = self.classify_show(show)
                        if show_type == "podcast":
                            podcasts.append(show.get('name', 'Unknown Show'))
                        elif show_type == "audiobook":
                            audiobooks.append(show.get('name', 'Unknown Show'))

                    if not podcasts and not audiobooks:
                        detailed_prompt = (
                            "Based on your Spotify data, it appears that you haven't saved any podcasts or audiobooks yet."
                        )
                    else:
                        detailed_prompt = (
                            "Here are your saved shows:\n\n"
                            "Podcasts:\n"
                        )
                        for podcast in podcasts:
                            detailed_prompt += f"- {podcast}\n"

                        detailed_prompt += "\nAudiobooks:\n"
                        for audiobook in audiobooks:
                            detailed_prompt += f"- {audiobook}\n"

                        detailed_prompt += f"\nUser Query: {query}\nResponse:"
                        
                elif query_type == 'recent_tracks':
                    data = get_recently_played_tracks(access_token)
                    detailed_prompt = (
        "You are looking at the user's recently played tracks. By default, tell them about their 5 most recent tracks. "
        "If they specifically ask for more tracks in their query, tell them about more tracks. "
        "Be conversational but concise. \n"
        f"Here is the user's Spotify data:\n{data}\nUser Query: {query}"
    )

                elif query_type == 'artist_info':
                    # First get artist name
                    messages = [
                        {"role": "system", "content": "You are a helper that identifies artist names in questions. Return ONLY the artist name, nothing else."},
                        {"role": "user", "content": query}
                    ]

                    artist_response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=messages,
                        max_tokens=50
                    )
                    artist_name = artist_response.choices[0].message.content.strip()
                    print(f"Identified artist: {artist_name}")
                    
                    artist_info = search_artist(artist_name, access_token)
                    general_info = self.fetch_general_info("artist", artist_name, query)

                    if artist_info:
                        detailed_prompt = f"""
    Question: {query}
    Spotify data: Followers: {artist_info['followers']}, Genres: {', '.join(artist_info['genres'])}, Popularity: {artist_info['popularity']}/100
    General information: {general_info}
    """
                    else:
                        detailed_prompt = f"Sorry, I couldn't find information about '{artist_name}' on Spotify.\n"
                        if general_info:
                            detailed_prompt += f"However, here is some general information:\n{general_info}"

                    # Special handling for artist info messages
                    messages = [
                        {"role": "system", "content": "You are a helpful Spotify assistant. Answer the user's question naturally. If the question is about stats (followers/genres/popularity), use the Spotify data. For other questions about the artist (age, background, origin, etc.), use the general information provided."},
                        {"role": "user", "content": detailed_prompt}
                    ]

                elif query_type == 'album_info':
                    album_name = query.split("album")[-1].strip()
                    album_info = search_item(album_name, 'album', access_token)
                    general_info = self.fetch_general_info("album", album_name)
                    
                    detailed_prompt = (
                        f"Here is detailed information about {album_name}:\n"
                        f"Release Date: {album_info['release_date']}\nTotal Tracks: {album_info['total_tracks']}\n"
                        f"General Information: {general_info}"
                    )

                else:
                    detailed_prompt = f"Sorry, I couldn't classify your query '{query}'."

                #streaming code for all queries 
                messages = [
                    {"role": "system", "content": "You are a personal Spotify assistant."},
                    {"role": "user", "content": detailed_prompt}
                ]

                def stream_and_save():
                    full_response = ""
                    for chunk in self.stream_response(messages, max_tokens=1000):
                        full_response += chunk
                        yield chunk
                    
                    # After streaming is complete, save to memory
                    self.memory[session_id]["history"].append({"response": full_response})
                
                return stream_and_save()

            except OpenAIError as e:
                print(f"Error processing query with LLM: {e}")
                return iter(["Sorry, I couldn't process your request at this time."])
            except Exception as e:
                print(f"Unexpected error in process_query: {e}")
                return iter(["An unexpected error occurred."])

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
        
    def extract_content_details(self, query: str, query_type: str) -> Dict:
        """Extract content name and additional details from query using LLM"""
        # Customize prompt based on query type
        if query_type == 'track_info':
            system_content = """You are a helper that identifies track information in questions. 
            If the query specifies both track and artist, return in format: 'track_name by artist_name'
            If only track is specified, return just the track name.
            Return ONLY the extracted information, nothing else."""
        elif query_type == 'album_info':
            system_content = """You are a helper that identifies album information in questions. 
            If the query specifies both album and artist, return in format: 'album_name by artist_name'
            If only album is specified, return just the album name.
            Return ONLY the extracted information, nothing else."""
        else:
            system_content = """You are a helper that identifies item names in questions. 
            Return ONLY the exact name being asked about, nothing else."""

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=150
            )
            details = response.choices[0].message.content.strip()
            self.logger.info(f"Extracted details: {details}")
            
            # Only parse for artist filter in track and album queries when "by" is present
            if ' by ' in details and query_type in ['track_info', 'album_info']:
                name_part, artist_part = details.split(' by ', 1)
                return {
                    "query": name_part.strip(),
                    "filters": {"artist": artist_part.strip()}
                }
            
            # For all other cases, return just the query without filters
            return {
                "query": details,
                "filters": None
            }
                
        except Exception as e:
            self.logger.error(f"Error extracting content details: {e}")
            return {"query": query, "filters": None}
        
    def format_recommendations(self, tracks, include_previews=True, limit=10):
        """
        Format a list of track recommendations into a readable message.
        
        Args:
            tracks (list): List of track objects from Spotify API
            include_previews (bool): Whether to include preview URLs
            limit (int): Maximum number of tracks to include in the message
            
        Returns:
            str: Formatted message with track recommendations
        """
        if not tracks:
            return "I couldn't find any recommendations matching your criteria."
        
        message = "Here are some recommended songs based on your request:\n\n"
        
        for i, track in enumerate(tracks[:limit], 1):
            # Basic track info
            artists = ", ".join(artist['name'] for artist in track['artists'])
            album = track['album']['name']
            release_date = track['album'].get('release_date', 'N/A')
            
            # Format track details
            message += f"{i}. '{track['name']}' by {artists}\n"
            message += f"   Album: {album} ({release_date})\n"
            
            # Add popularity if available
            if 'popularity' in track:
                message += f"   Popularity: {'🔥' * (track['popularity'] // 20 + 1)}\n"
            
            # Add preview URL if available and requested
            if include_previews and track.get('preview_url'):
                message += f"   Preview: {track['preview_url']}\n"
            
            # Add Spotify URI for easy access
            message += f"   Open in Spotify: {track['external_urls'].get('spotify', '')}\n"
            
            message += "\n"
        
        # Add a footer with playlist info if there are more tracks
        if len(tracks) > limit:
            message += f"\nShowing {limit} of {len(tracks)} recommended tracks."
        
        return message
    
# class SpotifyClient:
#     def __init__(self, access_token):
#         self.access_token = access_token


        
#     def search_for_artist(self, artist_name):
#         # Call the imported search_artist function from helpers
#         return search_artist(artist_name, self.access_token)
    
#     def get_recommendations(self, artist_id=None, seed_genres=None, min_danceability=None, max_danceability=None, min_energy=None, max_energy=None, target_danceability=None, target_energy=None):
#         """
#         Fetch recommendations from the Spotify API based on artist ID, genres, and tunable parameters.
#         """
#         endpoint = "https://api.spotify.com/v1/recommendations"
#         params = {
#             "limit": 10,  # Example limit
#             "seed_artists": artist_id if artist_id else None,
#             "seed_genres": seed_genres if seed_genres else None,
#             "min_danceability": min_danceability,
#             "max_danceability": max_danceability,
#             "target_danceability": target_danceability,
#             "min_energy": min_energy,
#             "max_energy": max_energy,
#             "target_energy": target_energy
#         }
        
#         # Remove keys with None values to avoid sending them in the request
#         params = {k: v for k, v in params.items() if v is not None}

#         headers = {
#             "Authorization": f"Bearer {self.access_token}"
#         }

#         # Make the request to Spotify's API
#         response = requests.get(endpoint, headers=headers, params=params)

#         if response.status_code == 200:
#             recommendations = response.json()
#             return recommendations['tracks']  # Returns the recommended tracks
#         else:
#             return f"Error fetching recommendations: {response.status_code}"
     
    

