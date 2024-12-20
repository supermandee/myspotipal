from typing import Dict, List, Optional
from spotify_client import SpotifyClient

from logger_config import setup_logger
logger = setup_logger(__name__)


class SpotifyHelpers:
    def __init__(self, spotify_client: SpotifyClient):
        self.client = spotify_client

    def get_user_profile(self) -> Optional[Dict]:
        """Get processed user profile information"""
        profile = self.client.get_user_profile_raw()
        if not profile:
            return None
            
        return {
            'id': profile['id'],
            'display_name': profile.get('display_name'),
            'uri': profile['uri'],
            'followers': profile.get('followers', {}).get('total', 0),
            'images': [
                {
                    'url': image['url'],
                }
                for image in profile.get('images', [])
            ] if profile.get('images') else []
        }
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
    
    def get_saved_tracks(self) -> Optional[List[Dict]]:
        """Get processed user's saved tracks."""
        tracks_raw = self.client.get_saved_tracks_raw()
        if not tracks_raw or 'items' not in tracks_raw:
            return []

        return [
            {
                'name': item['track']['name'],
                'artists': [artist['name'] for artist in item['track']['artists']],
                'album': item['track']['album']['name'],
                'uri': item['track']['uri'],
            }
            for item in tracks_raw['items'] if 'track' in item and item['track']
        ]

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
                'publisher': show['show'].get('publisher', ''),
                'uri':show['show'].get('uri', '')
            }
            
            # Check if it's not an audiobook
            description = show_data['description'].lower()
            audiobook_keywords = ["audiobook", "narrator", "narrated by", "read by", "author"]
            is_audiobook = any(keyword in description for keyword in audiobook_keywords)
            
            if not is_audiobook:
                processed_shows.append(show_data)
        
        return processed_shows
    
    def get_saved_audiobooks(self) -> Optional[List[Dict]]:
        """
        Get user's saved audiobooks.
        """
        audiobooks_raw = self.client.get_saved_audiobooks_raw()

        if not audiobooks_raw or 'items' not in audiobooks_raw:
            return []

        return [
            {
                'id': item.get('id'),
                'name': item.get('name'),
                'authors': [author['name'] for author in item.get('authors', [])],
                'publisher': item.get('publisher'),
                'uri': item.get('uri'),
            }
            for item in audiobooks_raw['items'] if item
        ]

    def get_recently_played_tracks(self) -> Optional[List[Dict]]:
        """Get processed user's recently played tracks"""
        tracks = self.client.get_recently_played_tracks_raw()
        return [{
            'name': track['track']['name'],
            'uri': track['track']['uri'],
            'artists': [
                {
                    'name': artist['name'], 
                    'id': artist['id'],
                    'uri': artist['uri']
                } 
                for artist in track['track']['artists']
            ],
            'album': {
                'name': track['track']['album']['name'],
                'id': track['track']['album']['id'],
                'uri': track['track']['album']['uri']
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
            if not item:  # Skip if item is None or empty
                continue
                
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
    
    def create_playlist(self, name: str, public: bool = True, 
                   collaborative: bool = False, description: str = None) -> Optional[Dict]:
        """Create a new playlist for the authenticated user"""
        playlist = self.client.create_playlist_raw(name, public, collaborative, description)
        if not playlist:
            return None
            
        return {
            'id': playlist['id'],
            'name': playlist['name'],
            'uri': playlist['uri']
        }

    def add_songs_to_playlist(self, playlist_id: str, uris: List[str], position: Optional[int] = None) -> Optional[Dict]:
        """
        Add items to a playlist
        
        Args:
            playlist_id (str): The Spotify ID of the playlist
            uris (List[str]): List of Spotify URIs to add (tracks or episodes)
            position (Optional[int]): Position to insert items (0-based index)
            
        Returns:
            Optional[Dict]: Response containing snapshot_id if successful, None if failed
        """
        if len(uris) > 100:
            logger.warning(f"Cannot add more than 100 items at once. Truncating to first 100 items.")
            uris = uris[:100]
            
        result = self.client.add_songs_to_playlist_raw(playlist_id, uris, position)
        if not result:
            return None
            
        return {
            'snapshot_id': result.get('snapshot_id'),
            'status': 'success',
            'items_added': len(uris)
        }
    
    def remove_playlist_items(self, playlist_id: str, uris: List[str], snapshot_id: Optional[str] = None) -> Optional[Dict]:
        """
        Remove items from a playlist.

        Args:
            playlist_id (str): Spotify playlist ID.
            uris (List[str]): URIs of the tracks or episodes to remove.
            snapshot_id (Optional[str]): Snapshot ID for validation.

        Returns:
            Optional[Dict]: API response containing the snapshot_id of the playlist.
        """
        if len(uris) > 100:
            logger.warning(f"Cannot remove more than 100 items at once. Truncating to first 100 items.")
            uris = uris[:100]

        result = self.client.remove_playlist_items_raw(playlist_id, uris, snapshot_id)
        if not result:
            return None

        return {
            'snapshot_id': result.get('snapshot_id'),
            'status': 'success',
            'items_removed': len(uris)
        }
    
    def update_playlist_details(self, playlist_id: str, name: Optional[str] = None,
                                public: Optional[bool] = None, collaborative: Optional[bool] = None,
                                description: Optional[str] = None) -> Optional[Dict]:
        """
        Update playlist details.

        Args:
            playlist_id (str): Spotify playlist ID.
            name (Optional[str]): New playlist name.
            public (Optional[bool]): Public/private status.
            collaborative (Optional[bool]): Collaborative status.
            description (Optional[str]): New playlist description.

        Returns:
            Optional[Dict]: API response or None if failed.
        """
        payload = {}
        if name is not None:
            payload['name'] = name
        if public is not None:
            payload['public'] = public
        if collaborative is not None:
            payload['collaborative'] = collaborative
        if description is not None:
            payload['description'] = description

        result = self.client.update_playlist_details_raw(playlist_id, payload)
        if not result:
            return None

        return {
            "status": "success",
            "message": f"Playlist {playlist_id} updated successfully."
        }


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
