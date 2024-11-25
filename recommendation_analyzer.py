from openai import OpenAI
from typing import Dict, Optional, Set
import logging
import json
import math
from helpers import search_artist, search_item
import requests
import base64
from dotenv import load_dotenv
import os

class RecommendationAnalyzer:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.refresh_token = os.getenv('REFRESH_TOKEN')
        self.access_token = None
        self.logger = self._setup_logger()

        # Initialize OpenAI client
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("Missing OpenAI API Key in environment variables")
        
        # Initialize the OpenAI client
        self.client = OpenAI(api_key=openai_api_key)

        # Get initial access token
        self.refresh_access_token()
        
        # Define constants
        self.AVERAGE_SONG_DURATION_MS = 200000
        self.available_genres = self.get_available_genres()
        
        # Define valid Spotify attributes and their allowed ranges
        self.SPOTIFY_ATTRIBUTES = {
            "acousticness": {"type": "float", "range": [0, 1]},
            "danceability": {"type": "float", "range": [0, 1]},
            "duration_ms": {"type": "integer", "range": [0, None]},
            "energy": {"type": "float", "range": [0, 1]},
            "instrumentalness": {"type": "float", "range": [0, 1]},
            "key": {"type": "integer", "range": [0, 11]},
            "liveness": {"type": "float", "range": [0, 1]},
            "loudness": {"type": "float", "range": [None, None]},  # No specific range
            "mode": {"type": "integer", "range": [0, 1]},
            "popularity": {"type": "integer", "range": [0, 100]},
            "speechiness": {"type": "float", "range": [0, 1]},
            "tempo": {"type": "float", "range": [0, None]},
            "time_signature": {"type": "integer", "range": [3, 7]},
            "valence": {"type": "float", "range": [0, 1]}
        }

        # # Common attribute mappings for natural language
        # self.MOOD_MAPPINGS = {
        #     "upbeat": {
        #         "min_energy": 0.7,
        #         "min_valence": 0.6,
        #         "target_energy": 0.8,
        #         "target_tempo": 120
        #     },
        #     "relaxing": {
        #         "max_energy": 0.4,
        #         "target_valence": 0.5,
        #         "max_tempo": 100,
        #         "target_acousticness": 0.6
        #     },
        #     "workout": {
        #         "min_energy": 0.8,
        #         "min_tempo": 120,
        #         "target_energy": 0.9,
        #         "target_valence": 0.7
        #     },
        #     "study": {
        #         "max_energy": 0.4,
        #         "min_instrumentalness": 0.5,
        #         "target_energy": 0.3,
        #         "max_speechiness": 0.3
        #     },
        #     "party": {
        #         "min_danceability": 0.7,
        #         "min_energy": 0.7,
        #         "target_danceability": 0.8,
        #         "target_popularity": 70
        #     }
        # }
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("RecommendationAnalyzer")

    def validate_spotify_attribute(self, attr_name: str, value: any) -> Optional[tuple]:
        """
        Validates a Spotify attribute and returns the validated value and any warnings.
        Returns (valid_value, warning_message) or None if invalid.
        """
        # Extract base attribute and prefix (min_, max_, target_)
        parts = attr_name.split('_')
        if len(parts) < 2:
            return None
        
        prefix = parts[0]
        base_attr = '_'.join(parts[1:])

        if prefix not in ['min', 'max', 'target']:
            return None
        
        if base_attr not in self.SPOTIFY_ATTRIBUTES:
            return None

        attr_spec = self.SPOTIFY_ATTRIBUTES[base_attr]
        warning = None

        try:
            # Type conversion
            if attr_spec["type"] == "float":
                value = float(value)
            elif attr_spec["type"] == "integer":
                value = int(value)

            # Range validation
            min_val, max_val = attr_spec["range"]
            if min_val is not None and value < min_val:
                value = min_val
                warning = f"{attr_name} adjusted to minimum: {min_val}"
            elif max_val is not None and value > max_val:
                value = max_val
                warning = f"{attr_name} adjusted to maximum: {max_val}"

            return (value, warning)

        except (ValueError, TypeError):
            return None
        
    def get_available_genres(self) -> Set[str]:
        """
        Fetch available genre seeds from Spotify API
        """
        url = 'https://api.spotify.com/v1/recommendations/available-genre-seeds'
        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                genres = set(response.json().get('genres', []))
                self.logger.info(f"Loaded {len(genres)} available genre seeds")
                return genres
            elif response.status_code == 401:
                self.logger.warning("Access token expired. Attempting to refresh...")
                self.refresh_access_token()
                return self.get_available_genres()
            else:
                self.logger.error(f"Failed to fetch genres: {response.status_code}")
                return set()
        except Exception as e:
            self.logger.error(f"Error fetching genres: {e}")
            return set()

    def match_genre(self, genre: str) -> Optional[str]:
        """
        Match user input genre with available Spotify genres
        """
        genre_lower = genre.lower()
        
        # Direct match
        if genre_lower in self.available_genres:
            return genre_lower
            
        # Find closest match
        for available_genre in self.available_genres:
            if genre_lower in available_genre or available_genre in genre_lower:
                self.logger.info(f"Matched genre '{genre}' to '{available_genre}'")
                return available_genre
                
        self.logger.warning(f"No match found for genre: {genre}")
        return None

    def resolve_seeds(self, analysis: Dict) -> Dict:
        """
        Resolve artist names, track names, and genres to their respective Spotify IDs/valid genres
        """
        resolved = {}

        # Resolve artists using search_item function
        if 'seed_artists' in analysis:
            artist_ids = []
            for artist in analysis['seed_artists']:
                artist_info = search_item(artist, 'artist', self.access_token)
                if artist_info and 'id' in artist_info:
                    artist_ids.append(artist_info['id'])
                    self.logger.info(f"Resolved artist '{artist}' to ID: {artist_info['id']}")
            if artist_ids:
                resolved['seed_artists'] = artist_ids

        # Resolve tracks using search_item function
        if 'seed_tracks' in analysis:
            track_ids = []
            for track in analysis['seed_tracks']:
                track_info = None
                if isinstance(track, dict) and 'name' in track and 'artist' in track:
                    # Search with both track name and artist
                    query = f"track:{track['name']} artist:{track['artist']}"
                    track_info = search_item(query, 'track', self.access_token)
                else:
                    # Search with just track name
                    track_info = search_item(track, 'track', self.access_token)
                
                if track_info and 'id' in track_info:
                    track_ids.append(track_info['id'])
                    self.logger.info(f"Resolved track '{track}' to ID: {track_info['id']}")
            if track_ids:
                resolved['seed_tracks'] = track_ids

        # Resolve genres
        if 'seed_genres' in analysis:
            valid_genres = []
            for genre in analysis['seed_genres']:
                if matched_genre := self.match_genre(genre):
                    valid_genres.append(matched_genre)
            if valid_genres:
                resolved['seed_genres'] = valid_genres

        return resolved

    def truncate_seeds(self, analysis: Dict):
        """
        Ensure total number of seeds doesn't exceed 5
        """
        remaining = 5
        seed_types = ['seed_tracks', 'seed_artists', 'seed_genres']
        
        for seed_type in seed_types:
            if seed_type in analysis:
                can_take = min(remaining, len(analysis[seed_type]))
                analysis[seed_type] = analysis[seed_type][:can_take]
                remaining -= can_take
                if remaining == 0:
                    break

    # Modify your existing analyze_request method to include seed resolution
    def analyze_request(self, query: str) -> Optional[Dict]:
        """
        Analyze a music recommendation request and extract structured information.
        Now includes Spotify ID resolution and dynamic mood attribute mapping.
        """
        try:
            # Get initial analysis from the LLM
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": f"Analyze this request: {query}"}
                ],
                temperature=0.7
            )

            initial_analysis = json.loads(response.choices[0].message.content.strip())
            
            # Process duration and limit
            if 'duration_minutes' in initial_analysis:
                duration = initial_analysis['duration_minutes']
                song_count = math.ceil(duration * 60 * 1000 / self.AVERAGE_SONG_DURATION_MS)
                initial_analysis['limit'] = min(song_count, 100)
            elif 'limit' not in initial_analysis:
                initial_analysis['limit'] = 20

            # Validate attributes
            if 'attributes' in initial_analysis:
                initial_analysis['attributes'] = self.validate_attributes(initial_analysis['attributes'])

            # Resolve seeds to Spotify IDs and valid genres
            resolved_seeds = self.resolve_seeds(initial_analysis)
            
            # Combine everything into final analysis
            final_analysis = {
                'limit': initial_analysis.get('limit', 20),
                **resolved_seeds
            }

            # Add validated attributes if present
            if 'attributes' in initial_analysis:
                final_analysis['attributes'] = initial_analysis['attributes']

            # Ensure total seeds don't exceed 5
            self.truncate_seeds(final_analysis)

            self.logger.info(f"Final analysis: {json.dumps(final_analysis, indent=2)}")
            return final_analysis

        except Exception as e:
            self.logger.error(f"Error in analyze_request: {e}")
            return None


    def get_system_prompt(self) -> str:
        """
        Return the system prompt for GPT
        """
        return """You are a music recommendation system that analyzes user requests and extracts key information.
        Return a JSON object with these fields (omit if not mentioned):

        {
            "limit": integer (1-100, default 20),
            "seed_artists": list of artist names (max 5 total seeds),
            "seed_tracks": list of track names (max 5 total seeds),
            "seed_genres": list of genres (max 5 total seeds),
            "duration_minutes": integer (if time specified),
            "attributes": {
                "mood": string (identify mood/vibe if specified),
                // Include relevant audio features based on the identified mood
                // Use min_, max_, or target_ prefix for the range
                // For example, an "upbeat" mood might have:
                // "min_energy": 0.7, "min_valence": 0.6, "target_tempo": 120
                // A "relaxing" mood might have:
                // "max_energy": 0.4, "target_valence": 0.5, "target_acousticness": 0.6
                // Adjust the attributes based on your understanding of the mood
            }
        }
        
        For tracks, you can specify artist for better matching:
        "seed_tracks": [
            {"name": "Anti-Hero", "artist": "Taylor Swift"},
            "Shake It Off"  
        ]
        """
    
    def validate_attributes(self, attributes: Dict) -> Dict:
        """
        Validate attributes and their values based on Spotify's allowed ranges.
        """
        validated = {}
        warnings = []

        for attr_name, value in attributes.items():
            result = self.validate_spotify_attribute(attr_name, value)
            if result:
                validated_value, warning = result
                validated[attr_name] = validated_value
                if warning:
                    warnings.append(warning)
        
        if warnings:
            self.logger.warning("Attribute validations:\n" + "\n".join(warnings))
        
        return validated
    

    def refresh_access_token(self) -> bool:
        """Refresh the Spotify access token"""
        token_url = 'https://accounts.spotify.com/api/token'
        client_credentials = f"{self.client_id}:{self.client_secret}"
        client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()

        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }

        token_headers = {
            'Authorization': f'Basic {client_credentials_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            self.logger.debug("Attempting to refresh access token...")
            response = requests.post(token_url, data=token_data, headers=token_headers)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to refresh token: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False

            token_info = response.json()
            self.access_token = token_info['access_token']
            self.logger.info("Successfully refreshed access token")
            return True

        except Exception as e:
            self.logger.error(f"Error refreshing token: {str(e)}")
            return False

    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(level=logging.DEBUG)
        return logging.getLogger('spotify_search')
    
def test_analyzer():
    
    load_dotenv()

    analyzer = RecommendationAnalyzer()
    
    test_queries = [
        "best songs for pumped workout gym",
        # "I want relaxing songs for studying, not too loud",
        # "Songs like Taylor Swift but more upbeat",
        # "Create a 45-minute party playlist with high energy dance songs",
        # "I need focus music for 2 hours of work, instrumental preferred",
        # "Songs similar to 'Anti-Hero' but sadder",
        # "Give me tracks with high danceability and energy for a workout",
        # "I want a 15-minute meditation playlist with very low energy",
        # "Create a playlist mixing hip-hop and electronic genres",
        # "Find me some songs between 120-140 BPM for running"
    ]
    
    print("\nTesting Recommendation Analyzer\n" + "="*50)
    
    for query in test_queries:
        print(f"\nTest Query: {query}")
        print("-" * 50)
        
        result = analyzer.analyze_request(query)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Analysis failed")
        
        print("-" * 50)

if __name__ == "__main__":
    test_analyzer()