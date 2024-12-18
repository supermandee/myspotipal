import unittest
from llm_client import LLMClient
import os
from dotenv import load_dotenv
import time
from flask import Flask
from flask_caching import Cache
from spotify_client import get_top_items, get_followed_artists, get_user_playlists, get_saved_shows, get_recently_played_tracks

class TestChatbotMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize Flask app
        cls.app = Flask(__name__)
        cls.app.config['CACHE_TYPE'] = 'simple'
        
        # Initialize cache with app
        cls.cache = Cache()
        cls.cache.init_app(cls.app)
        
        # Create app context
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # Initialize other components
        load_dotenv()
        cls.llm_client = LLMClient()
        cls.session_id = cls.llm_client.generate_session_id()
        cls.access_token = os.getenv('SPOTIFY_ACCESS_TOKEN')
        
        # Gather initial Spotify data
        with cls.app.app_context():
            cls.spotify_data = {
                'top_artists': {},
                'top_tracks': {}
            }
            
            # Get data for different time ranges
            time_ranges = ['short_term', 'medium_term', 'long_term']
            for time_range in time_ranges:
                cls.spotify_data['top_artists'][time_range] = get_top_items(cls.access_token, time_range, 'artists')
                cls.spotify_data['top_tracks'][time_range] = get_top_items(cls.access_token, time_range, 'tracks')
            
            # Cache the data
            cls.cache.set('spotify_data', cls.spotify_data)
    
    @classmethod
    def tearDownClass(cls):
        # Clean up
        cls.app_context.pop()
    
    def collect_response(self, response_generator):
        """Collect all chunks from the response generator into a single string"""
        return ''.join(list(response_generator))
    
    def test_basic_memory(self):
        """Test if bot remembers immediate previous question"""
        print("\nTesting basic memory...")
        
        # First query
        response1 = self.collect_response(
            self.llm_client.process_query(
                "What is your favorite color?",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"First response: {response1}")
        
        # Follow-up query
        response2 = self.collect_response(
            self.llm_client.process_query(
                "What did I just ask you about?",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"Follow-up response: {response2}")
        
        self.assertIn("color", response2.lower())
    
    def test_artist_memory(self):
        """Test if bot remembers previously mentioned artists"""
        print("\nTesting artist memory...")
        
        # Get top artists
        response1 = self.collect_response(
            self.llm_client.process_query(
                "Tell me your top 3 favorite artists",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"First response: {response1}")
        
        # Ask about mentioned artists
        response2 = self.collect_response(
            self.llm_client.process_query(
                "From the artists you just mentioned, which one has the highest popularity?",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"Follow-up response: {response2}")
        
        # Extract artists from first response and verify they're mentioned in second response
        artists_found = False
        for artist in self.extract_artists(response1):
            if artist.lower() in response2.lower():
                artists_found = True
                break
        
        self.assertTrue(artists_found, "Second response did not reference any artists from first response")
    
    def test_context_switch(self):
        """Test if bot maintains context across topic changes"""
        print("\nTesting context switch memory...")
        
        # Get most played song
        response1 = self.collect_response(
            self.llm_client.process_query(
                "What's my most played song?",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"First response: {response1}")
        
        # Change topic
        response2 = self.collect_response(
            self.llm_client.process_query(
                "Tell me about Drake",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"Topic change response: {response2}")
        
        # Return to original topic
        response3 = self.collect_response(
            self.llm_client.process_query(
                "Going back to my most played song, who is the artist?",
                self.spotify_data,
                self.access_token,
                self.session_id
            )
        )
        print(f"Return to original topic response: {response3}")
        
        # Extract song info from first response
        song_info = self.extract_song_info(response1)
        if song_info['artist']:
            self.assertIn(song_info['artist'].lower(), response3.lower())
    
    def extract_artists(self, response):
        """Helper method to extract artist names from response"""
        # Split response into words and look for capitalized words that might be artist names
        words = response.split()
        potential_artists = []
        current_name = []
        
        for word in words:
            if word[0].isupper():
                current_name.append(word)
            elif current_name:
                if len(current_name) > 0:
                    potential_artists.append(' '.join(current_name))
                current_name = []
        
        if current_name:  # Add last name if exists
            potential_artists.append(' '.join(current_name))
            
        return potential_artists
    
    def extract_song_info(self, response):
        """Helper method to extract song and artist information"""
        # Look for patterns like "song by artist" or "artist - song"
        song_info = {'song': '', 'artist': ''}
        
        # Split response into sentences
        sentences = response.split('.')
        for sentence in sentences:
            if 'by' in sentence:
                parts = sentence.split('by')
                if len(parts) == 2:
                    song_info['song'] = parts[0].strip()
                    song_info['artist'] = parts[1].strip()
                    break
        
        return song_info

if __name__ == '__main__':
    unittest.main(verbosity=2)