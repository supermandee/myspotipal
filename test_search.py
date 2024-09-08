import requests
import base64
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('REFRESH_TOKEN')

# Debugging: Check if environment variables are loaded properly
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"CLIENT_SECRET: {CLIENT_SECRET}")
print(f"REFRESH_TOKEN: {REFRESH_TOKEN}")

def refresh_access_token():
    """
    Refresh Spotify access token using the refresh token from environment variables.
    """
    token_url = 'https://accounts.spotify.com/api/token'
    client_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()

    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN  # Using the refresh token from .env
    }

    token_headers = {
        'Authorization': f'Basic {client_credentials_b64}'
    }

    response = requests.post(token_url, data=token_data, headers=token_headers)
    token_info = response.json()

    if response.status_code != 200:
        print("Error refreshing token:")
        print("Error code:", response.status_code)
        print("Error response:", response.text)
        return None

    return token_info['access_token']

def search_item(query, search_type, access_token):
    """
    Search for a specific item type on Spotify (e.g., album, artist).
    """
    url = 'https://api.spotify.com/v1/search'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'q': query,
        'type': search_type,
        'limit': 1
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Error searching for {search_type}: {response.status_code}")
        return None

    return response.json()

def test_album_search():
    """
    Test search for an album.
    """
    access_token = refresh_access_token()  # Refresh the access token using the refresh token
    if not access_token:
        print("Unable to refresh access token.")
        return

    album_name = "short'n sweet"  # Example album
    result = search_item(album_name, 'album', access_token)

    if result:
        print(f"Album found: {result}")
    else:
        print("No album found.")

if __name__ == '__main__':
    test_album_search()