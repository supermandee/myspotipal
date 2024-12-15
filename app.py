from flask import Response, Flask, redirect, request, url_for, session, render_template, jsonify
from flask import stream_with_context
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
import flash
import sys

from logger_config import setup_logger
logger = setup_logger(__name__)

# Define REDIRECT_URI at the top-level
REDIRECT_URI = os.getenv('REDIRECT_URI', "http://localhost:5001/callback")

# Load environment variables from .env file
load_dotenv()

def generate_session_id():
    return str(uuid.uuid4())


app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_APP_SECRET_KEY')

# Configure Flask-Caching
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 3600})  # Cache timeout set to 1 hour

# Configure session timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')


# Initialize the LLM client
llm_client = LLMClient()


def refresh_token():
    token_url = 'https://accounts.spotify.com/api/token'
    refresh_token = session.get('refresh_token') or os.getenv('SPOTIFY_REFRESH_TOKEN')
    if not refresh_token:
        logger.error("No refresh token available")
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

    try:
        response = requests.post(token_url, data=token_data, headers=token_headers)
        token_info = response.json()

        if response.status_code != 200:
            logger.error(f"Error refreshing token: {response.status_code}")
            logger.error(f"Error response: {response.text}")
            # Clear invalid session data
            session.pop('access_token', None)
            session.pop('refresh_token', None)
            session.pop('user_profile', None)
            return None

        session['access_token'] = token_info['access_token']
        if 'refresh_token' in token_info:
            session['refresh_token'] = token_info['refresh_token']
            update_env_variable('REFRESH_TOKEN', token_info['refresh_token'])
        
        # Update last refresh time
        session['token_refresh_time'] = datetime.now().timestamp()
        return token_info['access_token']

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error refreshing token: {str(e)}")
        return None

def check_auth_state():
    """Check authentication state and return appropriate response"""
    access_token = session.get('access_token')
    if not access_token:
        return {
            'authenticated': False,
            'message': 'No active session found',
            'action': 'login'
        }
    
    # Test if the token is valid
    try:
        response = requests.get(
            'https://api.spotify.com/v1/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if response.status_code == 401:
            # Try to refresh the token
            new_token = refresh_token()
            if not new_token:
                return {
                    'authenticated': False,
                    'message': 'Session expired. Please log in again',
                    'action': 'login'
                }
            return {
                'authenticated': True,
                'message': 'Token refreshed successfully',
                'action': None
            }
        elif response.status_code != 200:
            return {
                'authenticated': False,
                'message': 'Authentication error. Please log in again',
                'action': 'login'
            }
        
        return {
            'authenticated': True,
            'message': 'Authenticated',
            'action': None
        }
    except requests.exceptions.RequestException:
        return {
            'authenticated': False,
            'message': 'Network error. Please try again',
            'action': 'retry'
        }

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
    
# Catch all 500 errors
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the exception with traceback
    logger.error(f"Unhandled exception occurred {e}", exc_info=True)

    # Optionally, return a custom error response
    return jsonify({"error": f"An internal server error occurred, error logged {e}"}), 500


@app.route('/')
def index():
    logger.info("Rendering index page.")
    return render_template('index.html')


def debug_spotify_auth(request_data=None, response_data=None, stage='pre-auth'):
    """
    Comprehensive debugging function for Spotify authentication process
    """
    env = os.getenv('ENV', 'development')  # Default to development
    if env != 'development':
        return  # Skip logging unless in development mode

    logger.debug(f"=== Spotify Auth Debug - {stage} ===")
    
    def check_environment():
        required_vars = {
            'SPOTIFY_CLIENT_ID': CLIENT_ID,
            'SPOTIFY_CLIENT_SECRET': CLIENT_SECRET,
            'FLASK_APP_SECRET_KEY': app.secret_key
        }
        
        missing_vars = []
        for var_name, var_value in required_vars.items():
            if not var_value:
                missing_vars.append(var_name)
                logger.error(f"Missing environment variable: {var_name}")
            else:
                logger.debug(f"{var_name} is properly set")
        
        return len(missing_vars) == 0

    def check_session():
        session_vars = {
            'access_token': session.get('access_token'),
            'refresh_token': session.get('refresh_token'),
            'user_profile': session.get('user_profile')
        }
        
        logger.debug("Session state:")
        for var_name, var_value in session_vars.items():
            logger.debug(f"{var_name}: {'Present' if var_value else 'Missing'}")
        
        return all(session_vars.values())

    def check_callback_data(data):
        required_params = ['code']
        missing_params = []
        
        if not data:
            logger.error("No callback data provided")
            return False
            
        for param in required_params:
            if param not in data:
                missing_params.append(param)
                logger.error(f"Missing callback parameter: {param}")
        
        if 'error' in data:
            logger.error(f"Spotify auth error: {data['error']}")
            return False
            
        return len(missing_params) == 0

    def check_token_response(response_data):
        required_fields = ['access_token', 'token_type', 'scope']
        missing_fields = []
        
        if not response_data:
            logger.error("No token response data provided")
            return False
            
        for field in required_fields:
            if field not in response_data:
                missing_fields.append(field)
                logger.error(f"Missing token field: {field}")
        
        if 'error' in response_data:
            logger.error(f"Token error: {response_data['error']}")
            logger.error(f"Error description: {response_data.get('error_description', 'No description')}")
            return False
            
        return len(missing_fields) == 0

    # Check immediate environment and session state
    env_ok = check_environment()
    session_ok = check_session()
    
    logger.debug(f"Environment check: {'OK' if env_ok else 'FAILED'}")
    logger.debug(f"Session check: {'OK' if session_ok else 'FAILED'}")
    
    return {
        'environment_check': env_ok,
        'session_check': session_ok,
        'stage': stage
    }


# Updated routes with debugging
@app.route('/login')
def login():
    logger.debug("This is a test log message for the login route") 
    global REDIRECT_URI
    debug_result = debug_spotify_auth(stage='pre-auth')
    if not debug_result['environment_check']:
        logger.error("Environment check failed")
        return "Authentication configuration error", 500
        
    scope = 'user-read-private user-read-email user-top-read user-library-read user-follow-read playlist-read-private playlist-read-collaborative user-read-recently-played playlist-modify-public playlist-modify-private'
    params = {
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': scope
    }
    
    logger.debug(f"Login Parameters: {params}")
    logger.debug(f"REDIRECT_URI being used: {REDIRECT_URI}")
    url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    logger.debug(f"Full authorization URL: {url}")

    return redirect(url)

@app.route('/callback')
def callback():
    global REDIRECT_URI
    debug_result = debug_spotify_auth(request.args, stage='callback')
    
    # Log environment check results
    if not debug_result['environment_check']:
        missing_vars = debug_result.get('missing_vars', [])
        
        # Log missing variables to appropriate logger
        for var in missing_vars:
            if var.startswith('SPOTIFY_'):
                logger.error(f"Missing Spotify environment variable: {var}")
            else:
                logger.error(f"Missing application environment variable: {var}")
        
        return "Authentication configuration error", 500

    # Handle Spotify auth errors
    if 'error' in request.args:
        logger.error(f"Spotify auth error: {request.args.get('error')}")
        return f"Authentication error: {request.args.get('error')}", 400

    # Check for authorization code
    code = request.args.get('code')
    if not code:
        logger.error("No authorization code received")
        return "No authorization code received", 400

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
    
    try:
        # Request access and refresh tokens
        r = requests.post(token_url, data=token_data, headers=token_headers)
        token_info = r.json()
        
        # Debug token response
        debug_spotify_auth(token_info, stage='token-response')
        
        # Handle token errors
        if 'error' in token_info:
            logger.error(f"Token error: {token_info.get('error')}")
            return f"Token error: {token_info.get('error')}", 400
        
        # Save tokens to session
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        
        # Fetch and store user profile data
        headers = {
            'Authorization': f'Bearer {session["access_token"]}'
        }
        user_profile = requests.get('https://api.spotify.com/v1/me', headers=headers).json()
        session['user_profile'] = user_profile
        
        # Log successful profile fetch
        logger.info(f"Successfully fetched user profile: {user_profile.get('display_name', 'Unknown')}")
        
        # Save refresh token to .env
        refresh_token = token_info.get('refresh_token')
        if refresh_token:
            update_env_variable('REFRESH_TOKEN', refresh_token)
            logger.info("Refresh token successfully saved to .env")
        
        # Gather and cache Spotify data
        spotify_helper = get_spotify_client()
        spotify_data = spotify_helper.gather_spotify_data(cache)
        logger.info("Spotify data successfully gathered and cached")

        return redirect(url_for('chat'))
    
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Token request failed: {str(e)}")
        return f"Token request failed: {str(e)}", 500
    
    except KeyError as e:
        logger.error(f"Missing required session key: {str(e)}")
        return "Session error. Please log in again.", 500

@app.route('/loggedin')
def loggedin():
    # Check if the access token exists
    access_token = session.get('access_token')
    if not access_token:
        logger.warning("Attempt to access /loggedin without an access token")
        return redirect(url_for('index'))

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        # Fetch user profile from Spotify
        response = requests.get('https://api.spotify.com/v1/me', headers=headers)
        
        if response.status_code == 200:
            user_profile = response.json()
            logger.info(f"User profile fetched successfully: {user_profile.get('display_name', 'Unknown')}")
            return user_profile
        
        elif response.status_code == 401:  # Token is invalid or expired
            logger.warning("Access token is invalid or expired. Redirecting to login.")
            return redirect(url_for('index'))
        
        else:
            logger.error(f"Failed to fetch user profile. Status code: {response.status_code}")
            return f"Error fetching user profile. Status code: {response.status_code}", 500
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching user profile: {str(e)}")
        return "Network error occurred. Please try again later.", 500

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
    auth_state = check_auth_state()
    if not auth_state['authenticated']:
        flash(auth_state['message'])
        if auth_state['action'] == 'login':
            return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        # Check authentication state
        auth_state = check_auth_state()
        if not auth_state['authenticated']:
            logger.warning(f"Unauthenticated access attempt to /ask: {auth_state['message']}")
            return jsonify({
                "error": auth_state['message'],
                "redirect": url_for('login'),
                "needsAuth": True
            }), 401

        # Retrieve or create a session ID
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            logger.info(f"New session ID generated: {session_id}")

        # Get Spotify client helpers
        spotify_helpers = get_spotify_client()
        if not spotify_helpers:
            logger.error("Failed to create Spotify helpers. User may need to reauthenticate.")
            return jsonify({
                "error": "Unable to connect to Spotify. Please try logging in again",
                "redirect": url_for('login'),
                "needsAuth": True
            }), 401

        # Retrieve Spotify data from cache or fetch from API
        spotify_data = cache.get('spotify_data')
        if not spotify_data:
            logger.info("Spotify data not found in cache. Fetching fresh data.")
            spotify_data = spotify_helpers.gather_spotify_data(cache)
            if not spotify_data:
                logger.error("Failed to fetch Spotify data.")
                return jsonify({
                    "error": "Unable to fetch Spotify data. Please try logging in again",
                    "redirect": url_for('login'),
                    "needsAuth": True
                }), 401

        # Validate the query
        access_token = session.get('access_token')
        query = request.form.get('query')
        if not query:
            logger.warning("Received /ask request with no query provided.")
            return jsonify({"error": "No query provided"}), 400

        # stream response
        def generate():
            try:
                # Check token validity before starting
                access_token = ensure_valid_access_token()
                if not access_token:
                    yield f"data: Your session has expired. Please <a href='{url_for('login')}'>log in again</a>.\n\n"
                    return

                logger.info(f"Processing query: {query} with session ID: {session_id}")
                response_iterator = llm_client.process_query(query, spotify_data, access_token, session_id)

                for chunk in response_iterator:
                    yield chunk

            except requests.exceptions.RequestException as e:
                if "401" in str(e):
                    logger.warning("Session expired while processing /ask query.")
                    yield f"data: Your session has expired. Please <a href='{url_for('login')}'>log in again</a>.\n\n"
                else:
                    logger.error(f"Error processing query: {str(e)}", exc_info=True)
                    yield f"data: Error: {str(e)}. Please try again or <a href='{url_for('login')}'>log in again</a> if the problem persists.\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream'
        )

    except Exception as e:
        logger.error("Unexpected error occurred in /ask route.", exc_info=True)
        return jsonify({
            "error": "An unexpected error occurred. Please try again or log in again if the problem persists",
            "redirect": url_for('login'),
            "needsAuth": True
        }), 500
    
@app.route('/cached-data')
def cached_data():
    spotify_data = cache.get('spotify_data')
    if spotify_data:
        return jsonify(spotify_data)
    else:
        return jsonify({"error": "No data cached"}), 500

if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5001, debug=True)