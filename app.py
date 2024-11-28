from flask import Response, Flask, redirect, request, url_for, session, render_template, jsonify
from flask import stream_with_context
import markdown2
import requests
from urllib.parse import urlencode
import os
import base64
from dotenv import load_dotenv
from flask_caching import Cache

from datetime import timedelta
from spotify_client import SpotifyClient
from spotify_helpers import SpotifyHelpers
from llm_client import LLMClient
import uuid
import logging

# Load environment variables from .env file
load_dotenv()

def generate_session_id():
    return str(uuid.uuid4())

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_APP_SECRET_KEY')

# Configure Flask-Caching
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 3600})  # Cache timeout set to 1 hour

# Configure session timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

REDIRECT_URI = 'http://3.22.220.27/callback'

# Initialize the LLM client
llm_client = LLMClient()


def refresh_token():
    token_url = 'https://accounts.spotify.com/api/token'
    refresh_token = session.get('refresh_token') or os.getenv('SPOTIFY_REFRESH_TOKEN')
    if not refresh_token:
        print("No refresh token available")
        return None

    client_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()

    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
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

    session['access_token'] = token_info['access_token']
    if 'refresh_token' in token_info:
        session['refresh_token'] = token_info['refresh_token']
        update_env_variable('REFRESH_TOKEN', token_info['refresh_token'])
    return token_info['access_token']

def get_access_token():
    access_token = session.get('access_token')
    if not access_token:
        return None
    return access_token

def ensure_valid_access_token():
    access_token = get_access_token()
    if not access_token:
        return redirect(url_for('login'))

    # Test if the token is valid
    response = requests.get(
        'https://api.spotify.com/v1/me',
        headers={'Authorization': f'Bearer {access_token}'}
    )

    if response.status_code == 401:  # Token expired
        access_token = refresh_token()
        if not access_token:
            return None  # If refresh fails, return None

    return access_token

def update_env_variable(key, value):
    env_file = '.env'
    # Read current .env file contents
    lines = []
    updated = False
    with open(env_file, 'r') as file:
        lines = file.readlines()

    # Update the line if it exists or add a new one
    with open(env_file, 'w') as file:
        for line in lines:
            if line.startswith(f'{key}='):
                file.write(f'{key}={value}\n')
                updated = True
            else:
                file.write(line)
        if not updated:
            file.write(f'{key}={value}\n')

# Create a function to get or create SpotifyClient with current token
def get_spotify_client():
    access_token = ensure_valid_access_token()
    if not access_token:
        return None
    spotify_client = SpotifyClient(access_token)
    return SpotifyHelpers(spotify_client)  # Return SpotifyHelpers instance instead

@app.route('/get_refresh_token')
def get_refresh_token():
    refresh_token = session.get('refresh_token')
    if refresh_token:
        return f"Refresh Token: {refresh_token}", 200
    else:
        return "No refresh token found", 400

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    scope = 'user-read-private user-read-email user-top-read user-library-read user-follow-read playlist-read-private playlist-read-collaborative user-read-recently-played'
    params = {
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': scope
    }
    url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return redirect(url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_url = 'https://accounts.spotify.com/api/token'
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    client_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()

    token_headers = {
        'Authorization': f'Basic {client_credentials_b64}'
    }

    r = requests.post(token_url, data=token_data, headers=token_headers)
    token_info = r.json()
    session['access_token'] = token_info['access_token']
    session['refresh_token'] = token_info['refresh_token']

    # Fetch and store user profile data
    headers = {
        'Authorization': f'Bearer {session["access_token"]}'
    }
    user_profile = requests.get('https://api.spotify.com/v1/me', headers=headers).json()
    session['user_profile'] = user_profile

    # Save refresh token to .env
    refresh_token = token_info.get('refresh_token')
    if refresh_token:
        update_env_variable('REFRESH_TOKEN', refresh_token)

    # Gather and cache Spotify data using the new SpotifyHelpers class
    spotify_helper = get_spotify_client()
    spotify_data = spotify_helper.gather_spotify_data(cache)
    
    return redirect(url_for('chat'))

@app.route('/loggedin')
def loggedin():
    access_token = session.get('access_token')
    if access_token:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        user_profile = requests.get('https://api.spotify.com/v1/me', headers=headers).json()
        return user_profile
    return redirect(url_for('index'))

@app.route('/top-items')
def top_items():
    spotify_helper = get_spotify_client()  
    if not spotify_helper:
        return redirect(url_for('login'))
    
    time_ranges = ['short_term', 'medium_term', 'long_term']
    top_artists_data = {}
    top_tracks_data = {}

    for time_range in time_ranges:
        artists = spotify_helper.get_top_items(time_range, 'artists')
        if artists is None:
            return f"Error fetching top artists for {time_range}", 500
        
        genre_count = {}
        for artist in artists:
            for genre in artist['genres']:
                genre_count[genre] = genre_count.get(genre, 0) + 1
        
        top_genres = sorted(genre_count, key=genre_count.get, reverse=True)
        
        top_artists_data[time_range] = {
            'artists': artists,
            'genres': top_genres
        }
        
        tracks = spotify_helper.get_top_items(time_range, 'tracks')
        if tracks is None:
            return f"Error fetching top tracks for {time_range}", 500

        top_tracks_data[time_range] = tracks

    return render_template('top_items.html', top_artists_data=top_artists_data, top_tracks_data=top_tracks_data)

@app.route('/followed-artists')
def followed_artists():
    spotify_helpers = get_spotify_client()
    if not spotify_helpers:
        return redirect(url_for('login'))

    artists = spotify_helpers.get_followed_artists()
    if artists is None:
        return "Error fetching followed artists", 500

    return render_template('followed_artists.html', artists=artists)

@app.route('/playlists')
def playlists():
    spotify_helpers = get_spotify_client()
    if not spotify_helpers:
        return redirect(url_for('login'))

    playlists = spotify_helpers.get_user_playlists()
    if playlists is None:
        return "Error fetching playlists", 500

    return render_template('playlists.html', playlists=playlists)

@app.route('/saved-shows')
def saved_shows():
    spotify_helpers = get_spotify_client()
    if not spotify_helpers:
        return redirect(url_for('login'))

    shows = spotify_helpers.get_saved_shows()
    if shows is None:
        return "Error fetching saved shows", 500

    return render_template('saved_shows.html', shows=shows)

@app.route('/recent-tracks')
def recent_tracks():
    spotify_helpers = get_spotify_client()
    if not spotify_helpers:
        return redirect(url_for('login'))

    recent_tracks_data = spotify_helpers.get_recently_played_tracks()
    if recent_tracks_data is None:
        return "Error fetching recently played tracks", 500

    return render_template('recent_tracks.html', recent_tracks=recent_tracks_data)

@app.route('/chat')
def chat():
    return render_template('chat.html')

# Configure logging at the start of your application
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/ask', methods=['POST'])
def ask():
    try:
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id

        spotify_helpers = get_spotify_client()
        if not spotify_helpers:
            return jsonify({"error": "Please log in again", "redirect": url_for('login')}), 401

        spotify_data = cache.get('spotify_data')
        if not spotify_data:
            logging.debug("Spotify data not in cache. Fetching from Spotify API.")
            spotify_data = spotify_helpers.gather_spotify_data(cache)
            if not spotify_data:
                return jsonify({"error": "No Spotify data available"}), 401

        access_token = get_access_token()
        query = request.form.get('query')
        if not query:
            return jsonify({"error": "No query provided"}), 400

        def generate():
            try:
                response_iterator = llm_client.process_query(query, spotify_data, access_token, session_id)
                # Buffer to accumulate markdown content
                buffer = ""
                for chunk in response_iterator:
                    buffer += chunk
                    # Convert markdown to HTML and yield
                    html = markdown2.markdown(buffer, extras=['fenced-code-blocks', 'tables'])
                    yield f"data: {html}\n\n"
            except Exception as e:
                logging.exception("Error while processing query.")
                yield f"data: Error: {str(e)}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream'
        )

    except Exception as e:
        logging.exception("Unexpected error in /ask route.")
        return jsonify({"error": "Internal Server Error"}), 500
    

@app.route('/cached-data')
def cached_data():
    spotify_data = cache.get('spotify_data')
    if spotify_data:
        return jsonify(spotify_data)
    else:
        return jsonify({"error": "No data cached"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0')
