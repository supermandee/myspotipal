import requests
from typing import Optional, List, Dict, Any

from logger_config import setup_logger
logger = setup_logger(__name__)


class SpotifyClient:
    def __init__(self, access_token: str):
        # Add debug prints inside __init__ where we know they'll be executed
        print("=== SPOTIFY LOGGER DEBUG ===")
        print(f"Logger name: {logger.name}")
        print(f"Logger level: {logger.level}")
        print("Handlers:")
        for h in logger.handlers:
            print(f"- Handler: {type(h).__name__}")
            print(f"  Level: {h.level}")
            print(f"  Formatter: {h.formatter._fmt if h.formatter else 'None'}")

        self.access_token = access_token
        self.base_url = 'https://api.spotify.com/v1'
        self.headers = {
            'Authorization': f'Bearer {access_token}'
        }
        logger.warning("LOGGER WARNING TEST")

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
            """
            Make a GET request to the Spotify API
            """
            url = f'{self.base_url}/{endpoint}'
            logger.debug(f"Making request to {endpoint} with params: {params}")
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Error making request to {endpoint}:")
                logger.error(f"Status Code: {response.status_code}")
                logger.error(f"Response Text: {response.text}")
                return None
            
            logger.debug(f"Successful response from {endpoint}")
            return response.json()
    
    def _make_post_request(self, endpoint: str, json: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a POST request to the Spotify API
        """
        url = f'{self.base_url}/{endpoint}'
        logger.debug(f"Making POST request to {endpoint} with json: {json}")
        
        response = requests.post(url, headers=self.headers, json=json)
        
        if response.status_code not in [200, 201]:
            logger.error(f"Error making POST request to {endpoint}:")
            logger.error(f"Status Code: {response.status_code}")
            logger.error(f"Response Text: {response.text}")
            return None
        
        logger.debug(f"Successful response from {endpoint}")
        return response.json()
    
    def _paginate_request(self, endpoint: str, params: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Handle pagination for Spotify API requests
        """
        logger.debug(f"Starting paginated request to {endpoint} with limit {limit}")
        items = []
        url = f'{self.base_url}/{endpoint}'
        
        while url and (limit is None or len(items) < limit):
            logger.debug(f"Fetching page from {url}")
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Error in pagination for {endpoint}:")
                logger.error(f"Status Code: {response.status_code}")
                return items
                
            data = response.json()
            
            # Handle different response structures
            if 'items' in data:
                items.extend(data['items'])
            elif endpoint.startswith('me/following') and 'artists' in data:
                items.extend(data['artists']['items'])
            
            # Update URL for next page
            url = data.get('next') if 'next' in data else data.get('artists', {}).get('next')
            params = None  # Clear params for subsequent requests
            
            logger.debug(f"Collected {len(items)} items so far")
            
            if limit and len(items) >= limit:
                items = items[:limit]
                break
        
        logger.info(f"Completed paginated request to {endpoint}, collected {len(items)} items")
        return items
    
    def get_user_profile_raw(self) -> Dict:
            """Get raw API response for user's profile"""
            logger.info("Getting user profile")
            try:
                response = self._make_request('me')  
                logger.info(f"Retrieved profile for user: {response.get('display_name', 'Unknown')}")
                return response
            except Exception as e:
                logger.error(f"Failed to get user profile: {str(e)}")
                return {}

    def get_top_items_raw(self, time_range: str, item_type: str) -> Optional[Dict]:
        """Get raw API response for user's top artists or tracks"""
        logger.info(f"Getting top {item_type} for time range {time_range}")
        return self._make_request(f'me/top/{item_type}', {'time_range': time_range})

    def get_followed_artists_raw(self) -> List[Dict]:
        """Get raw API response for user's followed artists"""
        logger.info("Getting user's followed artists")
        artists = self._paginate_request('me/following', {'type': 'artist', 'limit': 50})
        logger.info(f"Retrieved {len(artists)} followed artists")
        return artists

    def get_user_playlists_raw(self, limit: int = 100) -> List[Dict]:
        """Get raw API response for user's playlists"""
        logger.info(f"Getting user's playlists (limit: {limit})")
        playlists = self._paginate_request('me/playlists', {'limit': 50}, limit)
        logger.info(f"Retrieved {len(playlists)} playlists")
        return playlists

    def get_saved_podcasts_raw(self) -> List[Dict]:
        """Get raw API response for user's saved shows"""
        logger.info("Getting user's saved podcasts")
        podcasts = self._paginate_request('me/shows', {'limit': 50})
        logger.info(f"Retrieved {len(podcasts)} saved podcasts")
        return podcasts

    def get_recently_played_tracks_raw(self) -> List[Dict]:
        """Get raw API response for user's recently played tracks"""
        logger.info("Getting user's recently played tracks")
        tracks = self._paginate_request('me/player/recently-played', {'limit': 50})
        logger.info(f"Retrieved {len(tracks)} recently played tracks")
        return tracks

    def search_item_raw(self, query: str, search_type: str, filters: Optional[Dict] = None) -> Optional[Dict]:
        """Get raw API response for search query"""
        logger.info(f"Searching for {search_type} with query: {query}")
        if filters:
            logger.debug(f"Applied filters: {filters}")
        
        query_parts = [query]
        if filters:
            query_parts.extend(
                f'{key}:"{value}"' if isinstance(value, str) else f'{key}:{value}'
                for key, value in filters.items()
                if value
            )
        
        params = {
            'q': ' '.join(query_parts),
            'type': search_type,
            'limit': 10
        }
        
        result = self._make_request('search', params)
        if result:
            logger.info(f"Search completed successfully")
        return result
    
    def create_playlist_raw(self, name: str, public: bool = True, 
                        collaborative: bool = False, description: str = None) -> Optional[Dict]:
        """Create a new playlist for the authenticated user"""
        payload = {
            'name': name,
            'public': public,
            'collaborative': collaborative
        }
        if description:
            payload['description'] = description

        return self._make_post_request('me/playlists', json=payload)

    def add_songs_to_playlist_raw(self, playlist_id: str, uris: List[str], position: Optional[int] = None) -> Optional[Dict]:
        """Add items to a playlist"""
        logger.info(f"Adding {len(uris)} items to playlist {playlist_id}")
        
        # Construct payload
        payload = {'uris': uris}
        if position is not None:
            payload['position'] = position
        
        endpoint = f'playlists/{playlist_id}/tracks'
        
        return self._make_post_request(endpoint, json=payload)
    
    def remove_playlist_items_raw(self, playlist_id: str, uris: List[str], snapshot_id: Optional[str] = None) -> Optional[Dict]:
        """Remove items from a playlist."""
        url = f'playlists/{playlist_id}/tracks'
        payload = {'tracks': [{'uri': uri} for uri in uris]}
        if snapshot_id:
            payload['snapshot_id'] = snapshot_id

        logger.info(f"Removing {len(uris)} items from playlist {playlist_id}")
        response = requests.delete(f'{self.base_url}/{url}', headers=self.headers, json=payload)

        if response.status_code != 200:
            logger.error(f"Failed to remove items from playlist {playlist_id}. Status: {response.status_code}, Response: {response.text}")
            return None

        return response.json()
    
    def get_saved_audiobooks_raw(self, limit: int = 20, offset: int = 0) -> Optional[Dict]:
        """
        Get raw API response for user's saved audiobooks.
        """
        logger.info(f"Getting user's saved audiobooks with limit {limit} and offset {offset}")
        return self._make_request('me/audiobooks', {'limit': limit, 'offset': offset})
    
    def get_saved_tracks_raw(self, limit: int = 50, offset: int = 0) -> Optional[Dict]:
        """
        Get raw API response for user's saved tracks.
        """
        params = {'limit': limit, 'offset': offset}
        return self._make_request('me/tracks', params)
    

