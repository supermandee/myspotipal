from openai import OpenAI
from typing import Dict, List, Optional
import requests
import math

class MusicRecommender:
    def __init__(self, openai_client: OpenAI, spotify_access_token: str):
        self.openai_client = openai_client
        self.spotify_access_token = spotify_access_token

    def analyze_music_request(self, query: str) -> Dict:
        """
        Analyze any music recommendation request, whether for playlist or single recommendations
        """
        prompt = f"""
        Analyze this music request and extract key information as JSON:
        "{query}"
        
        Extract:
        1. Purpose (playlist/recommendation)
        2. Activity type (if any)
        3. Duration (in minutes) or number of songs wanted
        4. Mood/vibe keywords
        5. Tempo preference
        6. Preferred genres
        7. Energy level (1-10)
        8. Similar artists mentioned
        9. Additional preferences (instrumental, acoustic, etc.)
        
        Return only the JSON, no other text.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a music analysis assistant that returns only JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error analyzing request: {e}")
            return None

    def map_to_spotify_parameters(self, analysis: Dict) -> Dict:
        """
        Convert natural language analysis into Spotify API parameters
        """
        # Activity to tempo mapping
        activity_tempo = {
            "running": {"min_tempo": 140, "max_tempo": 180},
            "walking": {"min_tempo": 120, "max_tempo": 140},
            "studying": {"min_tempo": 60, "max_tempo": 100},
            "meditation": {"min_tempo": 60, "max_tempo": 80},
            "workout": {"min_tempo": 130, "max_tempo": 170}
        }

        # Calculate number of songs (either from duration or requested amount)
        if 'duration' in analysis:
            number_of_songs = math.ceil(analysis['duration'] / 3.5)  # Assuming average song is 3.5 minutes
        else:
            number_of_songs = analysis.get('number_of_songs', 10)  # Default to 10 songs

        # Map energy level to Spotify's 0-1 scale
        energy = min(analysis.get('energy_level', 5) / 10, 1.0)

        # Build parameters dict
        params = {
            "limit": min(number_of_songs, 50),  # Spotify's limit is 50
            "target_energy": energy
        }

        # Add tempo if activity is specified
        if activity := analysis.get('activity'):
            tempo_range = activity_tempo.get(activity, {"min_tempo": 120, "max_tempo": 140})
            params.update(tempo_range)

        # Add genres if specified
        if genres := analysis.get('genres'):
            params["seed_genres"] = genres

        # Add seed artists if specified
        if artists := analysis.get('similar_artists'):
            artist_ids = self.get_artist_ids(artists)
            if artist_ids:
                params["seed_artists"] = artist_ids

        # Add additional audio features if specified
        if analysis.get('acoustic'):
            params["target_acousticness"] = 0.8
        if analysis.get('instrumental'):
            params["target_instrumentalness"] = 0.8
        if analysis.get('danceability'):
            params["target_danceability"] = analysis['danceability']

        return params

    def get_artist_ids(self, artist_names: List[str]) -> List[str]:
        """
        Convert artist names to Spotify artist IDs
        """
        artist_ids = []
        headers = {"Authorization": f"Bearer {self.spotify_access_token}"}
        
        for name in artist_names[:2]:  # Limit to 2 artists as Spotify allows max 5 seed parameters
            try:
                response = requests.get(
                    f"https://api.spotify.com/v1/search",
                    headers=headers,
                    params={"q": name, "type": "artist", "limit": 1}
                )
                if response.status_code == 200:
                    results = response.json()
                    if results['artists']['items']:
                        artist_ids.append(results['artists']['items'][0]['id'])
            except Exception as e:
                print(f"Error getting artist ID for {name}: {e}")
                continue
                
        return artist_ids

    def get_recommendations(self, params: Dict) -> List[Dict]:
        """
        Get song recommendations from Spotify
        """
        endpoint = "https://api.spotify.com/v1/recommendations"
        headers = {"Authorization": f"Bearer {self.spotify_access_token}"}
        
        try:
            response = requests.get(endpoint, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()['tracks']
            else:
                print(f"Error getting recommendations: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error in get_recommendations: {e}")
            return None

    def format_recommendations(self, tracks: List[Dict], detailed: bool = False) -> str:
        """
        Format recommendation results into a readable string
        """
        if not tracks:
            return "Sorry, I couldn't find any recommendations."

        if detailed:
            result = "Here are your recommended tracks:\n\n"
            for i, track in enumerate(tracks, 1):
                artists = ", ".join(artist['name'] for artist in track['artists'])
                album = track['album']['name']
                result += f"{i}. {track['name']}\n"
                result += f"   Artist(s): {artists}\n"
                result += f"   Album: {album}\n"
                result += f"   Spotify URI: {track['uri']}\n\n"
        else:
            result = "Here are some songs you might like:\n"
            for i, track in enumerate(tracks[:10], 1):  # Limit to top 10 if not detailed
                artists = ", ".join(artist['name'] for artist in track['artists'])
                result += f"{i}. {track['name']} by {artists}\n"

        return result

    def recommend_music(self, query: str, detailed: bool = False) -> Dict:
        """
        Main method to handle music recommendations
        """
        # Analyze the request
        analysis = self.analyze_music_request(query)
        if not analysis:
            return {"success": False, "error": "Could not analyze request"}

        # Get Spotify parameters
        params = self.map_to_spotify_parameters(analysis)
        
        # Get recommendations
        tracks = self.get_recommendations(params)
        if not tracks:
            return {"success": False, "error": "Could not get recommendations"}

        # Format results
        formatted_response = self.format_recommendations(tracks, detailed)
        
        return {
            "success": True,
            "tracks": tracks,
            "formatted_response": formatted_response,
            "analysis": analysis
        }