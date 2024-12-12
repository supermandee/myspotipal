import json
from spotify_client import SpotifyClient
from spotify_helpers import SpotifyHelpers

from logger_config import setup_logger
logger = setup_logger(__name__)


SPOTIFY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Get the current user's Spotify profile information including display name, ID, URI, follower count, and profile images",
            "parameters": {
                "type": "object",
                "properties": {},
                "strict": True
                }
            }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_items",
            "description": "Get user's top artists or top tracks (most frequently played artists or tracks) based on number of plays within a time period for a specific time range, if no time range is provided, default to medium_term",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_range": {
                        "type": "string",
                        "enum": ["short_term", "medium_term", "long_term"],
                        "description": "Time range for top items"
                    },
                    "item_type": {
                        "type": "string",
                        "enum": ["artists", "tracks"],
                        "description": "Type of items to fetch"
                    }
                },
                "required": ["time_range", "item_type"],
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_followed_artists",
            "description": "Get list of artists the user follows",
            "parameters": {
                "type": "object",
                "properties": {},
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_playlists",
            "description": "Get user's saved and followed Spotify playlists",
            "parameters": {
                "type": "object",
                "properties": {},
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_saved_podcasts",
            "description": "Get user's saved podcasts",
            "parameters": {
                "type": "object",
                "properties": {},
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recently_played_tracks",
            "description": "Get the chronological history of tracks the user has listened to, ordered by most recent play date first",
            "parameters": {
                "type": "object",
                "properties": {},
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_item",
            "description": "Retrieves factual information about existing items on Spotify. Use this to look up specific tracks, albums, artists, or playlists. This function performs literal search queries and returns exact matches - it does NOT generate recommendations or suggestions. For music recommendations, use natural language generation instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "search_type": {
                        "type": "string",
                        "enum": ["track", "album", "artist", "playlist", "show", "episode", "audiobook"]
                    },
                    "filters": {
                        "type": "object",
                        "additionalProperties": True
                    }
                },
                "required": ["query", "search_type"],
                "strict": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_playlist",
            "description": "Create a new empty playlist for the authenticated Spotify user, the playlist can be public or private. It can be collaborative or non-collaborative. Ask for preferences, if no preferences are given, use default values. Description can be added.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "public": {"type": "boolean", "default": True},
                    "collaborative": {"type": "boolean", "default": False},
                    "description": {"type": "string"}
                },
                "required": ["name"],
                "strict": True
            }
        }
    }
]


class SpotifyFunctionHandler:
    def __init__(self, access_token: str):
        self.spotify_client = SpotifyClient(access_token)
        self.spotify_helpers = SpotifyHelpers(self.spotify_client)

    def execute_function(self, tool_call) -> dict:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if name == "get_top_items":
            return self.spotify_helpers.get_top_items(args["time_range"], args["item_type"])
        elif name == "get_user_profile": 
            return self.spotify_helpers.get_user_profile()
        elif name == "get_followed_artists":
            return self.spotify_helpers.get_followed_artists()
        elif name == "get_user_playlists":
            return self.spotify_helpers.get_user_playlists()
        elif name == "get_saved_podcasts":
            return self.spotify_helpers.get_saved_podcasts()
        elif name == "get_recently_played_tracks":
            return self.spotify_helpers.get_recently_played_tracks()
        elif name == "search_item":
            return self.spotify_helpers.search_item(
                args["query"], 
                args["search_type"], 
                args.get("filters")
            )
        elif name == "create_playlist":
            return self.spotify_helpers.create_playlist(
                name=args["name"],
                public=args.get("public", True),
                collaborative=args.get("collaborative", False),
                description=args.get("description")
            )
        else:
            raise ValueError(f"Unknown function: {name}")