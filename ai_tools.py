import json
from spotify_client import SpotifyClient
from spotify_helpers import SpotifyHelpers

SPOTIFY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_items",
            "description": "Get user's top artists or tracks for a specific time range",
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
            "description": "Get user's Spotify playlists",
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
            "name": "get_saved_shows",
            "description": "Get user's saved podcasts and audiobooks",
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
            "description": "Get user's recently played tracks",
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
            "description": "Search for any item type on Spotify",
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
        elif name == "get_followed_artists":
            return self.spotify_helpers.get_followed_artists()
        elif name == "get_user_playlists":
            return self.spotify_helpers.get_user_playlists()
        elif name == "get_saved_shows":
            return self.spotify_helpers.get_saved_shows()
        elif name == "get_recently_played_tracks":
            return self.spotify_helpers.get_recently_played_tracks()
        elif name == "search_item":
            print("DEBUG! - search_item")
            return self.spotify_helpers.search_item(
                args["query"], 
                args["search_type"], 
                args.get("filters")
            )
        else:
            raise ValueError(f"Unknown function: {name}")