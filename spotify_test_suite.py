import requests
import logging
import base64
import os
from typing import Optional, List, Dict, Union
from urllib.parse import quote
from dotenv import load_dotenv

class SpotifySearcher:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.refresh_token = os.getenv('REFRESH_TOKEN')
        self.access_token = None
        self.logger = self._setup_logger()
        
        # Keep your existing search types
        self.SEARCH_TYPES = {
            'album': ['artist', 'year', 'album', 'upc', 'tag:new', 'tag:hipster'],
            'artist': ['artist', 'year', 'genre'],
            'track': ['artist', 'year', 'album', 'genre', 'isrc', 'track'],
            'playlist': [],
            'show': [],
            'episode': [],
            'audiobook': []
        }
        
        # Get initial access token
        self.refresh_access_token()

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

    # Keep all your existing methods exactly as they are
    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(level=logging.DEBUG)
        return logging.getLogger('spotify_search')

    def build_query(self, 
                   base_query: str,
                   filters: Optional[Dict[str, Union[str, int, List[int]]]] = None) -> str:
        # Keep your existing build_query method exactly as is
        if not filters:
            return quote(base_query)
            
        query_parts = [base_query]
        
        for filter_name, filter_value in filters.items():
            if filter_value:
                if filter_name == 'year' and isinstance(filter_value, list):
                    if len(filter_value) == 2:
                        query_parts.append(f"year:{filter_value[0]}-{filter_value[1]}")
                elif filter_name in ['tag:new', 'tag:hipster']:
                    if filter_value:
                        query_parts.append(filter_name)
                else:
                    query_parts.append(f"{filter_name}:{filter_value}")
        
        return quote(' '.join(query_parts))

    def search(self,
              query: str,
              search_types: List[str],
              filters: Optional[Dict] = None,
              limit: int = 20,
              offset: int = 0,
              market: Optional[str] = None,
              include_external: Optional[str] = None) -> Optional[Dict]:
        """
        Perform a comprehensive Spotify search with filters and options.
        Now includes automatic token refresh on 401 errors.
        """
        # Validate search types
        valid_types = set(self.SEARCH_TYPES.keys())
        if not all(t in valid_types for t in search_types):
            self.logger.error(f"Invalid search type(s). Valid types are: {valid_types}")
            return None

        formatted_query = self.build_query(query, filters)
        url = 'https://api.spotify.com/v1/search'
        
        def make_request():
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            params = {
                'q': formatted_query,
                'type': ','.join(search_types),
                'limit': min(50, max(1, limit)),
                'offset': offset
            }
            
            if market:
                params['market'] = market
            if include_external:
                params['include_external'] = include_external

            return requests.get(url, headers=headers, params=params)

        try:
            self.logger.debug(f"Sending request - URL: {url}")
            response = make_request()
            
            # Handle token expiration
            if response.status_code == 401:
                self.logger.debug("Token expired, refreshing...")
                if self.refresh_access_token():
                    response = make_request()  # Retry with new token
                else:
                    return None

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 'unknown')
                self.logger.error(f"Rate limit exceeded. Retry after: {retry_after} seconds")
                return None
            elif response.status_code != 200:
                self.logger.error(f"Error searching: Status Code: {response.status_code}")
                self.logger.error(f"Response Text: {response.text}")
                return None

            data = response.json()
            
            # Process results using your existing _process_item method
            results = {}
            for search_type in search_types:
                type_key = f"{search_type}s"
                if type_key in data:
                    items = data[type_key]['items']
                    results[type_key] = [self._process_item(item, search_type) for item in items]
            
            return results

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None

    def _process_item(self, item: Dict, item_type: str) -> Dict:
            """Process different types of Spotify items"""
            if item_type == 'artist':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'genres': item.get('genres', []),
                    'followers': item.get('followers', {}).get('total'),
                    'popularity': item.get('popularity'),
                    'images': item.get('images', []),
                    'uri': item['uri']
                }
            
            elif item_type == 'track':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in item['artists']],
                    'album': {
                        'id': item['album']['id'],
                        'name': item['album']['name'],
                        'release_date': item['album'].get('release_date')
                    },
                    'duration_ms': item.get('duration_ms'),
                    'popularity': item.get('popularity'),
                    'preview_url': item.get('preview_url'),
                    'uri': item['uri']
                }
            
            elif item_type == 'album':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'artists': [{'id': a['id'], 'name': a['name']} for a in item['artists']],
                    'release_date': item.get('release_date'),
                    'total_tracks': item.get('total_tracks'),
                    'images': item.get('images', []),
                    'uri': item['uri']
                }
            
            elif item_type == 'playlist':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'owner': {
                        'id': item['owner']['id'],
                        'name': item['owner'].get('display_name', 'Unknown')
                    },
                    'total_tracks': item['tracks']['total'],
                    'description': item.get('description'),
                    'images': item.get('images', []),
                    'uri': item['uri']
                }
            
            elif item_type == 'show':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'description': item.get('description'),
                    'publisher': item.get('publisher'),
                    'media_type': item.get('media_type'),
                    'total_episodes': item.get('total_episodes'),
                    'languages': item.get('languages', []),
                    'images': item.get('images', []),
                    'explicit': item.get('explicit', False),
                    'uri': item['uri']
                }
            
            elif item_type == 'episode':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'description': item.get('description'),
                    'duration_ms': item.get('duration_ms'),
                    'languages': item.get('languages', []),
                    'release_date': item.get('release_date'),
                    'explicit': item.get('explicit', False),
                    'show': {
                        'id': item['show'].get('id'),
                        'name': item['show'].get('name'),
                        'publisher': item['show'].get('publisher')
                    } if 'show' in item else None,
                    'images': item.get('images', []),
                    'uri': item['uri']
                }
            
            elif item_type == 'audiobook':
                return {
                    'id': item['id'],
                    'name': item['name'],
                    'authors': [author['name'] for author in item.get('authors', [])],
                    'narrators': [narrator['name'] for narrator in item.get('narrators', [])],
                    'description': item.get('description'),
                    'publisher': item.get('publisher'),
                    'languages': item.get('languages', []),
                    'total_chapters': item.get('total_chapters'),
                    'duration_ms': item.get('duration_ms'),
                    'explicit': item.get('explicit', False),
                    'images': item.get('images', []),
                    'uri': item['uri']
                }
            
            # Default case for unknown types
            return {
                'id': item['id'],
                'name': item['name'],
                'uri': item['uri']
            }
def test_advanced_search():
    """Test the advanced search functionality"""
    import json
    
    # Create searcher instance - no need to pass access_token anymore
    searcher = SpotifySearcher()
    
    # Keep your existing test cases
    test_cases = [
        {
            "name": "Basic artist search",
            "query": "Taylor Swift",
            "types": ["artist"],
            "filters": None
        },
        {
            "name": "Track search with filters",
            "query": "Doxy",
            "types": ["track"],
            "filters": {
                "artist": "Miles Davis",
                "year": 1955
            }
        },
        {
            "name": "Album search with tags",
            "query": "indie",
            "types": ["album"],
            "filters": {
                "tag:hipster": True,
                "year": [2020, 2023]
            }
        },
        {
            "name": "Multi-type search",
            "query": "Bad Guy",
            "types": ["track", "artist"],
            "filters": {
                "artist": "Billie Eilish"
            }
        },
        # New test cases for shows, episodes, and audiobooks
        {
            "name": "Popular podcast search",
            "query": "Crime Junkie",
            "types": ["show"],
            "filters": None
        },
        {
            "name": "Episode search",
            "query": "True Crime",
            "types": ["episode"],
            "filters": None
        },
        {
            "name": "Audiobook search",
            "query": "Harry Potter Stephen Fry",
            "types": ["audiobook"],
            "filters": None
        },
        {
            "name": "Show and Episode combined",
            "query": "Serial",
            "types": ["show", "episode"],
            "filters": None
        }
    ]
    
    for test in test_cases:
        print(f"\nRunning test: {test['name']}")
        print("-" * 50)
        
        results = searcher.search(
            query=test['query'],
            search_types=test['types'],
            filters=test['filters'],
            limit=3
        )
        
        if results:
            print(json.dumps(results, indent=2))
        else:
            print("No results found")

if __name__ == "__main__":
    test_advanced_search()