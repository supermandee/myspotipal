import requests
import base64
import os
from typing import Optional, List, Dict, Union
from urllib.parse import quote
from dotenv import load_dotenv

class SpotifySearcher:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.refresh_token = os.getenv('REFRESH_TOKEN')
        self.access_token = None
        self.logger = self._setup_logger()
        self.refresh_access_token()

    def _setup_logger(self):
        logging.basicConfig(level=logging.DEBUG)
        return logging.getLogger('spotify_searcher')

    def build_query(self, query: str, filters: Optional[Dict] = None) -> str:
        """
        Build a search query using Spotify's query syntax
        """
        query_parts = []
        
        # Add the track name as an exact match if it ends with a period
        if query.endswith('.'):
            query_parts.append(f'track:"{query}"')
        else:
            query_parts.append(f'track:{query}')
        
        # Add filters
        if filters:
            for key, value in filters.items():
                if value:
                    if key == 'artist':
                        # Add artist as an exact match
                        query_parts.append(f'artist:"{value}"')
                    else:
                        query_parts.append(f'{key}:{value}')
        
        # Join with spaces and return without additional encoding
        return ' '.join(query_parts)

    def search(self, 
              query: str,
              search_types: List[str],
              filters: Optional[Dict] = None,
              limit: int = 20,
              market: Optional[str] = None) -> Optional[Dict]:
        """
        Perform a Spotify search with correct query formatting
        """
        if not self.access_token:
            if not self.refresh_access_token():
                return None

        url = 'https://api.spotify.com/v1/search'
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        # Build the query string
        query_str = self.build_query(query, filters)
        self.logger.debug(f"Search query: {query_str}")
        
        params = {
            'q': query_str,
            'type': ','.join(search_types),
            'limit': min(50, max(1, limit)),
            'market': market if market else 'US'
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            self.logger.debug(f"Full URL: {response.url}")
            
            if response.status_code == 401:
                if self.refresh_access_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, params=params)
                else:
                    return None

            if response.status_code != 200:
                self.logger.error(f"Search failed: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return None

            return response.json()

        except Exception as e:
            self.logger.error(f"Search error: {str(e)}")
            return None

    def refresh_access_token(self) -> bool:
        """Refresh the Spotify access token"""
        token_url = 'https://accounts.spotify.com/api/token'
        client_credentials = f"{self.client_id}:{self.client_secret}"
        client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {client_credentials_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }

        try:
            response = requests.post(token_url, headers=headers, data=data)
            if response.status_code == 200:
                self.access_token = response.json()['access_token']
                return True
            return False
        except Exception as e:
            self.logger.error(f"Token refresh error: {str(e)}")
            return False

def test_search():
    searcher = SpotifySearcher()
    
    # Test case for ROSÉ's APT
    test_cases = [
        {
            "query": "APT.",
            "types": ["track"],
            "filters": {
                "artist": "ROSÉ"
            }
        }
    ]
    
    for test in test_cases:
        print(f"\nSearching for: {test['query']} by {test['filters'].get('artist', 'any artist')}")
        print("-" * 50)
        
        results = searcher.search(
            query=test["query"],
            search_types=test["types"],
            filters=test["filters"]
        )
        
        if results and 'tracks' in results:
            if len(results['tracks']['items']) == 0:
                print("No tracks found")
            for track in results['tracks']['items']:
                print(f"Found track: {track['name']}")
                print(f"By: {', '.join(artist['name'] for artist in track['artists'])}")
                print(f"Album: {track['album']['name']}")
                print(f"Release date: {track['album'].get('release_date', 'N/A')}")
                print("-" * 50)
        else:
            print("No results found or error in search")

if __name__ == "__main__":
    test_search()