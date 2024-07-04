from flask import Flask, redirect, request, url_for, session, render_template
import requests
from urllib.parse import urlencode
import os
import base64
from dotenv import load_dotenv
from helpers import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows  # Import helper functions


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_APP_SECRET_KEY')

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

REDIRECT_URI = 'http://localhost:5001/callback'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    scope = 'user-read-private user-read-email user-top-read user-library-read user-follow-read playlist-read-private playlist-read-collaborative'
    params = {
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': scope
    }
    #print(f"urlencode(params): {urlencode(params)}")
    url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    #print("Generated URL for login:", url)  # Debugging line
    return redirect(url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    #print("Authorization code:", code)  # Debugging line
    token_url = 'https://accounts.spotify.com/api/token'
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    client_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_credentials_b64 = base64.b64encode(client_credentials.encode()).decode()
    #print(client_credentials, client_credentials_b64)

    token_headers = {
        'Authorization': f'Basic {client_credentials_b64}'
    }

    r = requests.post(token_url, data=token_data, headers=token_headers)
    token_info = r.json()
    #print("Token response:", token_info) 
    session['access_token'] = token_info['access_token']
    return redirect(url_for('loggedin'))

@app.route('/loggedin')
def loggedin():
    access_token = session.get('access_token')
    #print("Access token:", access_token)
    if access_token:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        user_profile = requests.get('https://api.spotify.com/v1/me', headers=headers).json()
        return user_profile
    return redirect(url_for('index'))


@app.route('/top-items')
def top_items():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    time_ranges = ['short_term', 'medium_term', 'long_term']
    top_artists_data = {}
    top_tracks_data = {}

    for time_range in time_ranges:
        artists = get_top_items(access_token, time_range, 'artists')
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
        
        tracks = get_top_items(access_token, time_range, 'tracks')
        if tracks is None:
            return f"Error fetching top tracks for {time_range}", 500

        top_tracks_data[time_range] = tracks

    return render_template('top_items.html', top_artists_data=top_artists_data, top_tracks_data=top_tracks_data)



@app.route('/followed-artists')
def followed_artists():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    print("Access Token:", access_token)
    artists = get_followed_artists(access_token)
    if artists is None:
        return "Error fetching followed artists", 500

    print("Received artists data:", artists)  # Debugging line

    return render_template('followed_artists.html', artists=artists)

@app.route('/playlists')
def playlists():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    print("Access Token:", access_token)
    playlists = get_user_playlists(access_token)
    if playlists is None:
        return "Error fetching playlists", 500

    return render_template('playlists.html', playlists=playlists)

@app.route('/saved-shows')
def saved_shows():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    print("Access Token:", access_token)
    shows = get_saved_shows(access_token)
    if shows is None:
        return "Error fetching saved shows", 500

    return render_template('saved_shows.html', shows=shows)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)