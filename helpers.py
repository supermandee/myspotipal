import requests

def get_top_items(access_token, time_range, item_type):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/me/top/{item_type}?limit=50&time_range={time_range}', headers=headers)
    
    if response.status_code != 200:
        # Enhanced error logging
        print(f"Error fetching top {item_type} for {time_range}:")
        print("Error code:", response.status_code)
        print("Error response:", response.text)
        return None

    return response.json()['items']

def get_followed_artists(access_token):
    url = 'https://api.spotify.com/v1/me/following?type=artist&limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    artists = []
    while url and len(artists) < 100:
        print(f"Making request to URL: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching followed artists:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        print("Received data:", data)  # Debugging line
        
        artists.extend(data['artists']['items'])
        
        if len(artists) >= 100:
            break
        
        if 'cursors' in data['artists'] and 'after' in data['artists']['cursors']:
            after = data['artists']['cursors']['after']
            url = f'https://api.spotify.com/v1/me/following?type=artist&limit=50&after={after}'
        else:
            break

    return artists[:100]

def get_user_playlists(access_token):
    url = 'https://api.spotify.com/v1/me/playlists?limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    playlists = []
    while url and len(playlists) < 100:
        print(f"Making request to URL: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching user playlists:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        print("Received data:", data)
        
        playlists.extend(data['items'])
        
        if len(playlists) >= 100:
            break
        
        url = data['next']

    return playlists[:100]

def get_saved_shows(access_token):
    url = 'https://api.spotify.com/v1/me/shows?limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    shows = []
    while url:
        print(f"Making request to URL: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching saved shows:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        print("Received data:", data)
        
        shows.extend(data['items'])
        
        url = data['next']

    return shows

def get_recently_played_tracks(access_token):
    url = 'https://api.spotify.com/v1/me/player/recently-played?limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    recent_tracks = []
    while url:
        print(f"Making request to URL: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching recent tracks:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        print("Received data:", data)
        
        recent_tracks.extend(data['items'])
        
        url = data.get('next')

    return recent_tracks

