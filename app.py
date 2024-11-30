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
from logging.handlers import RotatingFileHandler


# Create loggers for different purposes
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')

# Create handlers with more specific naming
app_handler = RotatingFileHandler(
    "/var/log/myspotipal/app.log",
    maxBytes=10485760,  # 10MB
    backupCount=5
)
error_handler = RotatingFileHandler(
    "/var/log/myspotipal/error.log",
    maxBytes=10485760,
    backupCount=5
)
console_handler = logging.StreamHandler()

# Create formatter with process ID for better debugging
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(process)d] %(module)s: %(message)s')

# Apply formatter to all handlers
for handler in [app_handler, error_handler, console_handler]:
    handler.setFormatter(formatter)

# Configure loggers and handlers
app_logger.setLevel(logging.INFO)
app_logger.addHandler(app_handler)

error_logger.setLevel(logging.ERROR)
error_logger.addHandler(error_handler)
error_logger.addHandler(console_handler)

# Prevent propagation
app_logger.propagate = False
error_logger.propagate = False

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

@app.route('/')
def index():
    return render_template('index.html')


def debug_spotify_auth(request_data=None, response_data=None, stage='pre-auth'):
    """
    Comprehensive debugging function for Spotify authentication process
    Parameters:
        request_data: Dict containing request information
        response_data: Dict containing response information
        stage: String indicating which stage of auth process ('pre-auth', 'callback', 'token-refresh')
    """
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
    debug_result = debug_spotify_auth(stage='pre-auth')
    if not debug_result['environment_check']:
        logger.error("Environment check failed")
        return "Authentication configuration error", 500
        
    scope = 'user-read-private user-read-email user-top-read user-library-read user-follow-read playlist-read-private playlist-read-collaborative user-read-recently-played'
    params = {
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': scope
    }
    
    logger.debug(f"Login Parameters: {params}")
    url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return redirect(url)

@app.route('/callback')
def callback():
    debug_result = debug_spotify_auth(request.args, stage='callback')
    
    if not debug_result['environment_check']:
        logger.error("Environment check failed")
        return "Authentication configuration error", 500
    
    if 'error' in request.args:
        logger.error(f"Spotify auth error: {request.args.get('error')}")
        return f"Authentication error: {request.args.get('error')}", 400
        
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
        r = requests.post(token_url, data=token_data, headers=token_headers)
        token_info = r.json()
        
        debug_spotify_auth(token_info, stage='token-response')
        
        if 'error' in token_info:
            logger.error(f"Token error: {token_info.get('error')}")
            return f"Token error: {token_info.get('error')}", 400
        
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
        
        # Gather and cache Spotify data
        spotify_helper = get_spotify_client()
        spotify_data = spotify_helper.gather_spotify_data(cache)
        
        return redirect(url_for('chat'))
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Token request failed: {str(e)}")
        return f"Token request failed: {str(e)}", 500

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
    auth_state = check_auth_state()
    if not auth_state['authenticated']:
        flash(auth_state['message'])
        if auth_state['action'] == 'login':
            return redirect(url_for('login'))
    return render_template('chat.html')

# Configure logging at the start of your application
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/ask', methods=['POST'])
def ask():
    try:
        auth_state = check_auth_state()
        if not auth_state['authenticated']:
            return jsonify({
                "error": auth_state['message'],
                "redirect": url_for('login'),
                "needsAuth": True
            }), 401

        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id

        spotify_helpers = get_spotify_client()
        if not spotify_helpers:
            return jsonify({
                "error": "Unable to connect to Spotify. Please try logging in again",
                "redirect": url_for('login'),
                "needsAuth": True
            }), 401

        spotify_data = cache.get('spotify_data')
        if not spotify_data:
            logger.debug("Spotify data not in cache. Fetching from Spotify API.")
            spotify_data = spotify_helpers.gather_spotify_data(cache)
            if not spotify_data:
                return jsonify({
                    "error": "Unable to fetch Spotify data. Please try logging in again",
                    "redirect": url_for('login'),
                    "needsAuth": True
                }), 401

        access_token = session.get('access_token')
        query = request.form.get('query')
        if not query:
            return jsonify({"error": "No query provided"}), 400

        def generate():
            try:
                response_iterator = llm_client.process_query(query, spotify_data, access_token, session_id)
                buffer = ""
                for chunk in response_iterator:
                    buffer += chunk
                    html = markdown2.markdown(buffer, extras=['fenced-code-blocks', 'tables'])
                    yield f"data: {html}\n\n"
            except requests.exceptions.RequestException as e:
                if "401" in str(e):
                    yield f"data: Your session has expired. Please <a href='{url_for('login')}'>log in again</a>.\n\n"
                else:
                    logger.exception("Error while processing query.")
                    yield f"data: Error: {str(e)}. Please try again or <a href='{url_for('login')}'>log in again</a> if the problem persists.\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream'
        )

    except Exception as e:
        logger.exception("Unexpected error in /ask route.")
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
    app.run(host='0.0.0.0')
