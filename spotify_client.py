import requests
from typing import Optional, List, Dict, Any

class SpotifyClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = 'https://api.spotify.com/v1'
        self.headers = {
            'Authorization': f'Bearer {access_token}'
        }

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a GET request to the Spotify API
        """
        url = f'{self.base_url}/{endpoint}'
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            print(f"Error making request to {endpoint}:")
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None
            
        return response.json()

    def _paginate_request(self, endpoint: str, params: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Handle pagination for Spotify API requests
        """
        items = []
        url = f'{self.base_url}/{endpoint}'
        
        while url and (limit is None or len(items) < limit):
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error in pagination for {endpoint}:")
                print("Status Code:", response.status_code)
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
            
            if limit and len(items) >= limit:
                items = items[:limit]
                break

        return items

    def get_top_items_raw(self, time_range: str, item_type: str) -> Optional[Dict]:
        """Get raw API response for user's top artists or tracks"""
        return self._make_request(f'me/top/{item_type}', {'time_range': time_range})

    def get_followed_artists_raw(self) -> List[Dict]:
        """Get raw API response for user's followed artists"""
        return self._paginate_request('me/following', {'type': 'artist', 'limit': 50})

    def get_user_playlists_raw(self, limit: int = 100) -> List[Dict]:
        """Get raw API response for user's playlists"""
        return self._paginate_request('me/playlists', {'limit': 50}, limit)

    def get_saved_podcasts_raw(self) -> List[Dict]:
        """Get raw API response for user's saved shows"""
        return self._paginate_request('me/shows', {'limit': 50})

    def get_recently_played_tracks_raw(self) -> List[Dict]:
        """Get raw API response for user's recently played tracks"""
        return self._paginate_request('me/player/recently-played', {'limit': 50})

    def search_item_raw(self, query: str, search_type: str, filters: Optional[Dict] = None) -> Optional[Dict]:
        """Get raw API response for search query"""
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
        
        return self._make_request('search', params)