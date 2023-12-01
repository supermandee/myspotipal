from flask import Flask, redirect, request, url_for, session
import requests
from urllib.parse import urlencode
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_APP_SECRET_KEY')  # Replace with a secret key

CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID') # Replace with your Spotify Client ID
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')  # Replace with your Spotify Client Secret
REDIRECT_URI = 'http://localhost:5000/callback'

@app.route('/')
def index():
    return 'Want to find the perfect festival to go to?! <a href="/login">Log in with Spotify</a>'

@app.route('/login')
def login():
    scope = 'user-read-private user-read-email'
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
    token_headers = {
        'Authorization': f'Basic {requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET).encode()}'
    }
    r = requests.post(token_url, data=token_data, headers=token_headers)
    token_info = r.json()
    session['access_token'] = token_info['access_token']
    return redirect(url_for('loggedin'))

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

if __name__ == '__main__':
    app.run(debug=True)
