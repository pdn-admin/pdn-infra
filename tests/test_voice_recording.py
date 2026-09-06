import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO

# Import the Flask app and routes
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app import create_app


class TestVoiceRecording:
    """Test voice recording functionality"""
    
    @pytest.fixture
    def app(self):
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_voice_recording_frontend_features(self, client):
        """Test that voice recording features are present"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for voice recording variables
        assert 'mediaRecorder' in html
        assert 'audioChunks' in html
        assert 'speechRecognition' in html
        assert 'isRecording' in html
        
        # Check for voice recording functions
        assert 'startRecording' in html
        assert 'stopRecording' in html
        assert 'startSpeechRecognition' in html
        
        # Check for recording indicator styles
        assert 'recording-indicator' in html
        assert 'transcription-text' in html

    def test_audio_upload_route_exists(self, client):
        """Test that audio upload route exists"""
        response = client.post('/pdn-chat-ai/upload_audio')
        # Should return 400 (missing file) rather than 404 (route not found)
        assert response.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__]) 