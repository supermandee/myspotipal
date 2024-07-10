import requests

def get_top_items(access_token, time_range, item_type):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/me/top/{item_type}?&time_range={time_range}', headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching top {item_type} for {time_range}:")
        print("Error code:", response.status_code)
        print("Error response:", response.text)
        return None

    items = response.json()['items']
    # Keep only necessary fields
    simplified_items = []
    for item in items:
        simplified_item = {
            'name': item['name'],
            'popularity': item.get('popularity'),
        }
        if item_type == 'artists':
            simplified_item['genres'] = item['genres']
        elif item_type == 'tracks':
            simplified_item['artists'] = [artist['name'] for artist in item['artists']]
            simplified_item['album'] = item['album']['name']
        simplified_items.append(simplified_item)
    return simplified_items

def summarize_data(data, item_type):
    summary = {}
    if item_type == 'artists':
        genres = [genre for item in data for genre in item.get('genres', [])]
        summary['top_genres'] = list(set(genres))
    elif item_type == 'tracks':
        summary['top_artists'] = list(set(artist for item in data for artist in item.get('artists', [])))
    
    summary['average_popularity'] = sum(item.get('popularity', 0) for item in data) / len(data)
    return summary

def get_followed_artists(access_token):
    url = 'https://api.spotify.com/v1/me/following?type=artist&limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    artists = []
    while url and len(artists) < 100:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching followed artists:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        for artist in data['artists']['items']:
            simplified_artist = {
                'id': artist['id'],
                'name': artist['name'],
                'genres': artist['genres'],
                'popularity': artist.get('popularity'),
                'uri': artist['uri']
            }
            artists.append(simplified_artist)
        
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
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching user playlists:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        for playlist in data['items']:
            simplified_playlist = {
                'id': playlist['id'],
                'name': playlist['name'],
                'uri': playlist['uri']
            }
            playlists.append(simplified_playlist)
        
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
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching saved shows:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        for show in data['items']:
            simplified_show = {
                'id': show['show']['id'],
                'name': show['show']['name'],
                'description': show['show']['description'],
                'publisher': show['show']['publisher'],
                'uri': show['show']['uri']
            }
            shows.append(simplified_show)
        
        url = data['next']

    return shows

def get_recently_played_tracks(access_token):
    url = 'https://api.spotify.com/v1/me/player/recently-played?limit=50'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    recent_tracks = []
    while url:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Error fetching recent tracks:")
            print("Request URL:", url)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return None

        data = response.json()
        for track in data['items']:
            simplified_track = {
                'id': track['track']['id'],
                'name': track['track']['name'],
                'artists': [{'name': artist['name'], 'id': artist['id']} for artist in track['track']['artists']],
                'album': {'name': track['track']['album']['name'], 'id': track['track']['album']['id']},
                'played_at': track['played_at'],
                'uri': track['track']['uri']
            }
            recent_tracks.append(simplified_track)
        
        url = data.get('next')

    return recent_tracks

def gather_spotify_data(access_token, cache):
    # Fetch data using the helper functions
    time_ranges = ['short_term', 'medium_term', 'long_term']
    top_artists_data = {}
    top_tracks_data = {}

    for time_range in time_ranges:
        top_artists_data[time_range] = get_top_items(access_token, time_range, 'artists')
        top_tracks_data[time_range] = get_top_items(access_token, time_range, 'tracks')

    spotify_data = {
        'top_artists': top_artists_data,
        'top_tracks': top_tracks_data
    }

    print("Spotify data to be cached:", spotify_data)  # Debug statement
    cache.set('spotify_data', spotify_data)  # Explicitly cache the data
    return spotify_data