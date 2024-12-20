# MySpotiPal 🎵

## Your Personal Spotify AI Assistant

Hey there! Meet MySpotiPal - your AI-powered music buddy that knows your Spotify library inside out! Whether you're curious about your listening habits or seeking new musical discoveries, MySpotiPal is here to answer all your music-related questions! Engage in a fun, interactive way as you explore the diverse world of music tailored just for you!  ✨ 

## Tech Stack 🛠️
- Flask web application
- Spotify Web API
- OpenAI GPT-4
- Python
- HTML
- JavaScript

## What Can MySpotiPal Do? 🌟

## Playlist Generation & Management 🚀
```
"Can you create a playlist of bunker techno?"
"Please remove the song Sunset Lover from my playlist Beach Lounge Vibes"
"Create a playlist called '80s Rock' and add some hair metal classics from the 80s"
```
Automatically create playlists and manage them in your Spotify account; this includes adding and deleting tracks, updating the name, description, privacy and collaborative settings

### Check Your Music Taste 🎧
```
"Who are my top artists this month?"
"What have I been listening to lately?"
"Show me my all-time favorite artists"
```
MySpotiPal analyzes your listening habits across different timeframes (4 weeks, 6 months, or all time)

### Manage Your Spotify World 📚
```
"Who do I follow on Spotify?"
"Show me my playlists"
"What podcasts have I saved?" 
```
Keep track of your followed artists, playlists, recent plays, saved tracks, podcasts, and audiobooks etc

### Learn About Any Artist, Songs, Playlists, Podcasts & More 🎤
```
"How many followers does Billie Eilish have?"
"What genre is The Weeknd?"
"Tell me about BTS"
"Did Elon Musk appear on 'The Joe Rogan Experience'?"  
```
Get both general info and Spotify stats for any artist, song, audiobook and more!

### Get Music Recommendations 🎵
```
"Recommend me songs like Glass Animals"
"What should I listen to if I like indie rock?"
```

## Technical Setup 🛠️

### You'll Need:
- Python 3.8+
- Spotify Developer Account ([Get Started](https://developer.spotify.com/documentation/web-api))
- OpenAI API key ([Get Started](https://platform.openai.com/docs/api-reference/introduction))

### Quick Start:
1. Set up your environment:
```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
OPENAI_API_KEY=your_openai_key
FLASK_APP_SECRET_KEY=your_secret_key
TRACELOOP_API_KEY=your_traceloop_key
```

2. Get it running:
```bash
git clone https://github.com/supermandee/myspotipal.git
pip install -r requirements.txt
python app.py
```

## Good to Know 📝
- While you can follow unlimited artists on Spotify, the chat functionality processes a limited subset of your followed artists when answering queries.
- Data is always fresh from Spotify's API

## Want to Contribute? 💡
Got ideas for making MySpotiPal even better? Open a pull request or issue - let's make it awesome together!

## License

This project is licensed under the MIT License. See the [MIT License](./LICENSE.txt). file for more information.

