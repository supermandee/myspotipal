from typing import Dict, List, Optional
from spotify_client import SpotifyClient

from logger_config import setup_logger
logger = setup_logger(__name__)


class SpotifyHelpers:
    def __init__(self, spotify_client: SpotifyClient):
        self.client = spotify_client

    def get_top_items(self, time_range: str, item_type: str) -> Optional[List[Dict]]:
        """Get user's top artists or tracks"""
        response = self.client.get_top_items_raw(time_range, item_type)
        if not response:
            return None

        return [
            {
                'name': item['name'],
                'uri': item['uri'],
                'popularity': item.get('popularity'),
                **(
                    {'genres': item['genres']} if item_type == 'artists' 
                    else {
                        'artists': [artist['name'] for artist in item['artists']],
                        'album': item['album']['name']
                    } if item_type == 'tracks'
                    else {}
                )
            }
            for item in response['items']
        ]
    def get_followed_artists(self) -> Optional[List[Dict]]:
        """Get processed user's followed artists"""
        artists = self.client.get_followed_artists_raw()
        return [{'name': artist['name']} for artist in artists]

    def get_user_playlists(self, limit: int = 100) -> Optional[List[Dict]]:
        """Get processed user's playlists"""
        playlists = self.client.get_user_playlists_raw(limit)
        return [{
            'id': playlist['id'],
            'name': playlist['name'],
            'uri': playlist['uri']
        } for playlist in playlists if playlist is not None]

    def get_saved_podcasts(self) -> Optional[List[Dict]]:
        """Get processed user's saved shows, filtering for podcasts only"""
        shows = self.client.get_saved_podcasts_raw()
        processed_shows = []
        
        for show in shows:
            show_data = {
                'name': show['show'].get('name', 'Unknown Show'),
                'description': show['show'].get('description', ''),
                'publisher': show['show'].get('publisher', '')
            }
            
            # Check if it's not an audiobook
            description = show_data['description'].lower()
            audiobook_keywords = ["audiobook", "narrator", "narrated by", "read by", "author"]
            is_audiobook = any(keyword in description for keyword in audiobook_keywords)
            
            if not is_audiobook:
                processed_shows.append(show_data)
        
        return processed_shows

    def get_recently_played_tracks(self) -> Optional[List[Dict]]:
        """Get processed user's recently played tracks"""
        tracks = self.client.get_recently_played_tracks_raw()
        return [{
            'name': track['track']['name'],
            'artists': [{'name': artist['name'], 'id': artist['id']} 
                       for artist in track['track']['artists']],
            'album': {
                'name': track['track']['album']['name'],
                'id': track['track']['album']['id']
            }
        } for track in tracks]
    def search_item(self, query: str, search_type: str, filters: Optional[Dict] = None) -> Optional[List[Dict]]:
        """
        Search for items on Spotify and return detailed information for all results based on type
        """
        result = self.client.search_item_raw(query, search_type, filters)
        if not result:
            return None
        
        type_key = f"{search_type}s"
        items = result.get(type_key, {}).get('items', [])
        if not items:
            return None

        processed_items = []
        
        for item in items:
            processed_item = None
            
            if search_type == 'track':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'artists': [{'name': artist['name']} for artist in item['artists']],
                    'album': item['album']['name'],
                    'duration_ms': item.get('duration_ms'),
                    'popularity': item.get('popularity'),
                    'preview_url': item.get('preview_url'),
                    'explicit': item.get('explicit', False),
                    'uri': item['uri']
                }
            
            elif search_type == 'artist':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'genres': item.get('genres', []),
                    'followers': item.get('followers', {}).get('total'),
                    'popularity': item.get('popularity'),
                    'uri': item['uri']
                }
            
            elif search_type == 'album':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'artists': [{'name': artist['name']} for artist in item['artists']],
                    'release_date': item.get('release_date'),
                    'total_tracks': item.get('total_tracks'),
                    'uri': item['uri']
                }
            
            elif search_type == 'playlist':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'owner': item['owner'].get('display_name'),
                    'total_tracks': item['tracks']['total'],
                    'description': item.get('description'),
                    'uri': item['uri']
                }
            
            elif search_type == 'show':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'publisher': item.get('publisher'),
                    'description': item.get('description'),
                    'total_episodes': item.get('total_episodes'),
                    'uri': item['uri']
                }
            
            elif search_type == 'episode':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'show_name': item.get('show', {}).get('name'),
                    'description': item.get('description'),
                    'duration_ms': item.get('duration_ms'),
                    'release_date': item.get('release_date'),
                    'uri': item['uri']
                }
            
            elif search_type == 'audiobook':
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'authors': [author.get('name') for author in item.get('authors', [])],
                    'narrators': [narrator.get('name') for narrator in item.get('narrators', [])],
                    'description': item.get('description'),
                    'duration_ms': item.get('duration_ms'),
                    'uri': item['uri']
                }
            
            else:
                # Fallback for unknown types
                processed_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'uri': item['uri']
                }

            processed_items.append(processed_item)

        return processed_items

    def gather_spotify_data(self, cache) -> Dict[str, Dict]:
        """Gather all relevant Spotify data"""
        time_ranges = ['short_term', 'medium_term', 'long_term']
        spotify_data = {
            'top_artists': {
                range_: self.get_top_items(range_, 'artists')
                for range_ in time_ranges
            },
            'top_tracks': {
                range_: self.get_top_items(range_, 'tracks')
                for range_ in time_ranges
            }
        }
        
        cache.set('spotify_data', spotify_data)
        return spotify_data

    @staticmethod
    def _simplify_item(item: Dict, item_type: str) -> Dict:
        """Simplify item data structure"""
        simplified = {
            'name': item['name'],
            'popularity': item.get('popularity')
        }
        
        if item_type == 'artists':
            simplified['genres'] = item['genres']
        elif item_type == 'tracks':
            simplified['artists'] = [artist['name'] for artist in item['artists']]
            simplified['album'] = item['album']['name']
            
        return simplified
