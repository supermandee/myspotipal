from flask import Flask, redirect, request, url_for, session, render_template
import requests
from urllib.parse import urlencode
import os
import base64

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_APP_SECRET_KEY')  # Replace with a secret key

CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID') # Replace with your Spotify Client ID
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')  # Replace with your Spotify Client Secret

#print("Client ID:", CLIENT_ID)  # Debugging line
#print("Client Secret:", CLIENT_SECRET)  # Debugging line
REDIRECT_URI = 'http://localhost:5001/callback'

@app.route('/')
def index():
    return 'Want to find the perfect festival to go to?! <a href="/login">Log in with Spotify</a>'

@app.route('/login')
def login():
    scope = 'user-read-private user-read-email user-top-read'
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

@app.route('/top-artists')
def top_artists():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get('https://api.spotify.com/v1/me/top/artists?limit=50', headers=headers)
    
    if response.status_code != 200:
        # Enhanced error logging
        print("Error code:", response.status_code)
        print("Error response:", response.text)
        return f"Error fetching top artists: {response.text}", response.status_code

    top_artists_data = response.json()
    artists = top_artists_data['items']

    genre_count = {}
    for artist in artists:
        for genre in artist['genres']:
            genre_count[genre] = genre_count.get(genre, 0) + 1
    
    # Sort genres by frequency
    top_genres = sorted(genre_count, key=genre_count.get, reverse=True)
    
    # Now, render these artists and genres in a template or return as a JSON response
    return render_template('top_artists.html', artists=artists, genres=top_genres)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
