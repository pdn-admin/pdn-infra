import pytest
import json
import os
import logging
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO
from flask import Flask, jsonify
from hypothesis import given, settings
from hypothesis import strategies as st

# Import the Flask app and routes
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.pdn_chat_ai.logger import setup_logger
from app.pdn_chat_ai.chat_routes import (
    handle_errors,
    ValidationError,
    AuthenticationError,
    RateLimitExceeded,
)

try:
    from app.pdn_chat_ai.chat_routes import generate_ai_response
except ImportError:
    generate_ai_response = None


class TestChatImprovements:
    """Test class for chat interface improvements"""
    
    @pytest.fixture
    def app(self):
        """Create test app instance"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def auth_session(self, client):
        """Create authenticated session"""
        with client.session_transaction() as sess:
            sess['email'] = 'test@example.com'
            sess['user_name'] = 'Test User'
        return client

    def test_security_headers(self, client):
        """Test that security headers are properly set"""
        response = client.get('/pdn-chat-ai/')
        assert response.status_code == 200
        
        # Check for security headers in the HTML
        html = response.get_data(as_text=True)
        assert 'X-Content-Type-Options' in html
        assert 'X-Frame-Options' in html
        assert 'Content-Security-Policy' in html

    def test_dark_mode_support(self, client):
        """Test dark mode functionality"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        # Check for dark mode CSS variables
        assert '[data-theme="dark"]' in html
        assert '--primary-color' in html
        assert '--text-primary' in html

    def test_input_sanitization(self, client):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = '<script>alert("xss")</script>'
        
        with patch('app.pdn_chat_ai.chat_routes.generate_ai_response') as mock_generate:
            mock_generate.return_value = {"message": "Test response"}
            
            response = client.post('/pdn-chat-ai/chat', 
                                 json={'message': malicious_input, 'user_name': 'Test'})
            
            assert response.status_code == 200
            # Verify the sanitized input was passed to the AI function
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args[0]
            assert '<script>' not in call_args[0]  # message should be sanitized

    def test_file_upload_validation(self, client):
        """Test file upload validation"""
        # Test valid file
        valid_file = FileStorage(
            stream=BytesIO(b'test content'),
            filename='test.jpg',
            content_type='image/jpeg'
        )
        
        with patch('app.pdn_chat_ai.chat_routes.secure_filename') as mock_secure:
            mock_secure.return_value = 'test.jpg'
            
            response = client.post('/pdn-chat-ai/upload', 
                                 data={'file': valid_file})
            
            assert response.status_code == 200
            data = json.loads(response.get_data())
            assert 'filename' in data
            assert 'url' in data

    def test_file_upload_invalid_type(self, client):
        """Test file upload with invalid file type"""
        invalid_file = FileStorage(
            stream=BytesIO(b'test content'),
            filename='test.exe',
            content_type='application/x-executable'
        )
        
        response = client.post('/pdn-chat-ai/upload', 
                             data={'file': invalid_file})
        
        assert response.status_code == 400
        data = json.loads(response.get_data())
        assert 'error' in data
        assert 'not allowed' in data['error']

    def test_file_upload_too_large(self, client):
        """Test file upload with file too large"""
        # Create a mock file that appears to be 10MB
        large_file = FileStorage(
            stream=BytesIO(b'x' * (6 * 1024 * 1024)),  # 6MB content
            filename='large.jpg',
            content_type='image/jpeg'
        )
        
        with patch.object(large_file, 'tell', return_value=10 * 1024 * 1024):  # 10MB
            response = client.post('/pdn-chat-ai/upload', 
                                 data={'file': large_file})
            
            assert response.status_code == 400
            data = json.loads(response.get_data())
            assert 'error' in data
            assert 'too large' in data['error']

    def test_ai_response_generation(self):
        """Test AI response generation with different inputs"""
        # Test greeting response
        response = generate_ai_response('שלום', 'Test User', {})
        assert 'שלום Test User' in response['message']
        assert '🌿' in response['message']
        
        # Test PDN code response without context
        response = generate_ai_response('מה הקוד שלי?', 'Test User', {})
        assert 'קוד המקור' in response['message']
        assert 'שאלון' in response['message']
        
        # Test PDN code response with context
        context = {'pdn_code': '12345'}
        response = generate_ai_response('מה הקוד שלי?', 'Test User', context)
        assert '12345' in response['message']
        
        # Test spiritual response
        response = generate_ai_response('מדיטציה', 'Test User', {})
        assert 'מסע פנימי' in response['message']
        
        # Test help response
        response = generate_ai_response('עזרה', 'Test User', {})
        assert 'עוזר' in response['message']
        
        # Test default response
        response = generate_ai_response('random text', 'Test User', {})
        assert 'תודה' in response['message']
        assert 'Test User' in response['message']

    def test_error_handling(self, client):
        """Test error handling in chat endpoints"""
        # Test invalid JSON
        response = client.post('/pdn-chat-ai/chat', 
                             data='invalid json',
                             content_type='application/json')
        assert response.status_code == 400
        
        # Test empty message
        response = client.post('/pdn-chat-ai/chat', 
                             json={'message': '', 'user_name': 'Test'})
        assert response.status_code == 400
        
        # Test missing message
        response = client.post('/pdn-chat-ai/chat', 
                             json={'user_name': 'Test'})
        assert response.status_code == 400

    def test_chat_history_endpoint(self, client):
        """Test chat history endpoint"""
        response = client.get('/pdn-chat-ai/history')
        assert response.status_code == 200
        data = json.loads(response.get_data())
        assert 'history' in data

    def test_chat_settings_endpoint(self, client):
        """Test chat settings endpoint"""
        response = client.get('/pdn-chat-ai/settings')
        assert response.status_code == 200
        data = json.loads(response.get_data())
        # Should return settings or error message

    def test_accessibility_features(self, client):
        """Test accessibility features in the chat interface"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for ARIA labels
        assert 'aria-label' in html
        
        # Check for screen reader support
        assert 'sr-only' in html
        
        # Check for keyboard navigation
        assert 'onkeydown' in html
        
        # Check for focus management
        assert 'focus()' in html

    def test_responsive_design(self, client):
        """Test responsive design features"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for mobile responsive CSS
        assert '@media (max-width: 768px)' in html
        
        # Check for viewport meta tag
        assert 'viewport' in html

    def test_performance_features(self, client):
        """Test performance optimizations"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for message queue implementation
        assert 'messageQueue' in html
        
        # Check for loading indicators
        assert 'loading-spinner' in html
        
        # Check for proper error handling
        assert 'showError' in html

    def test_theme_persistence(self, client):
        """Test theme preference persistence"""
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for localStorage usage
        assert 'localStorage' in html
        
        # Check for theme toggle functionality
        assert 'toggleTheme' in html

    def test_file_upload_directory_creation(self, client):
        """Test that upload directory is created if it doesn't exist"""
        with patch('os.makedirs') as mock_makedirs:
            with patch('os.path.join') as mock_join:
                mock_join.return_value = '/test/upload/dir'
                
                valid_file = FileStorage(
                    stream=BytesIO(b'test content'),
                    filename='test.jpg',
                    content_type='image/jpeg'
                )
                
                with patch('app.pdn_chat_ai.chat_routes.secure_filename') as mock_secure:
                    mock_secure.return_value = 'test.jpg'
                    
                    client.post('/pdn-chat-ai/upload', data={'file': valid_file})
                    
                    # Verify directory creation was attempted
                    mock_makedirs.assert_called_once_with('/test/upload/dir', exist_ok=True)

    def test_unique_filename_generation(self, client):
        """Test unique filename generation for uploads"""
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = 'test123'
            
            valid_file = FileStorage(
                stream=BytesIO(b'test content'),
                filename='test.jpg',
                content_type='image/jpeg'
            )
            
            with patch('app.pdn_chat_ai.chat_routes.secure_filename') as mock_secure:
                mock_secure.return_value = 'test.jpg'
                
                response = client.post('/pdn-chat-ai/upload', data={'file': valid_file})
                
                if response.status_code == 200:
                    data = json.loads(response.get_data())
                    assert data['unique_filename'].startswith('test123_')

    def test_chat_message_queue(self, client):
        """Test message queue functionality"""
        # This would require more complex testing with WebSocket or similar
        # For now, we test the queue logic in the frontend
        response = client.get('/pdn-chat-ai/chat-ai?user_name=Test')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)
        
        # Check for queue implementation
        assert 'messageQueue' in html
        assert 'processMessageQueue' in html
        assert 'isProcessing' in html


class TestLoggerIdempotenceProperty:
    """Property-based tests for logger setup idempotence.

    **Validates: Requirements 5.3**
    """

    @given(
        logger_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='._-'),
            min_size=1,
            max_size=30,
        ),
        repeat_count=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_property_logger_setup_idempotence(self, logger_name, repeat_count):
        """Property 9: Logger Setup Idempotence

        For any logger name and N repeated calls (N >= 1), setup_logger returns
        a logger with exactly one handler (no duplicates).

        **Validates: Requirements 5.3**
        """
        # Clean up any pre-existing logger with this name to isolate the test
        if logger_name in logging.Logger.manager.loggerDict:
            existing = logging.getLogger(logger_name)
            existing.handlers.clear()

        # Call setup_logger N times with the same name
        for _ in range(repeat_count):
            logger = setup_logger(logger_name)

        # Verify exactly one handler exists regardless of how many times called
        assert len(logger.handlers) == 1, (
            f"Expected exactly 1 handler after {repeat_count} calls, "
            f"got {len(logger.handlers)} for logger '{logger_name}'"
        )

        # Verify the handler has the expected formatter pattern
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert '%(asctime)s' in handler.formatter._fmt
        assert '%(name)s' in handler.formatter._fmt
        assert '%(levelname)s' in handler.formatter._fmt
        assert '%(message)s' in handler.formatter._fmt

        # Verify logger name and level
        assert logger.name == logger_name
        assert logger.level == logging.INFO

        # Cleanup: remove handlers to avoid polluting other tests
        logger.handlers.clear()


class TestChatErrorToStatusMappingProperty:
    """Property-based tests for chat handle_errors decorator exception-to-status mapping.

    **Validates: Requirements 4.7**
    """

    @pytest.fixture
    def app(self):
        """Create test app instance"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        return app

    @given(
        error_msg=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=50)
    def test_property_error_decorator_exception_to_status_mapping(self, error_msg):
        """Property 8: Error Decorator Exception-to-Status Mapping (chat variant)

        For any exception type in {ValidationError→400, AuthenticationError→401,
        RateLimitExceeded→429, TimeoutError→503, Exception→500}, the handle_errors
        decorator returns the corresponding HTTP status code.

        **Validates: Requirements 4.7**
        """
        from app.pdn_chat_ai.chat_routes import (
            handle_errors, ValidationError, AuthenticationError, RateLimitExceeded
        )

        # Define the mapping of exception types to expected HTTP status codes
        exception_status_mapping = [
            (ValidationError(error_msg), 400),
            (AuthenticationError(error_msg), 401),
            (RateLimitExceeded(error_msg), 429),
            (TimeoutError(error_msg), 503),
            (Exception(error_msg), 500),
        ]

        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'

        for exc, expected_status in exception_status_mapping:
            # Create a decorated function that raises the specific exception
            @handle_errors
            def failing_endpoint():
                raise exc

            with app.test_request_context():
                result = failing_endpoint()
                # handle_errors returns (response, status_code)
                response, status_code = result
                assert status_code == expected_status, (
                    f"Expected status {expected_status} for {type(exc).__name__}('{error_msg}'), "
                    f"got {status_code}"
                )


class TestHandleErrorsDecorator:
    """Test the handle_errors decorator maps exceptions to correct HTTP status codes.

    Validates: Requirements 4.7
    """

    @pytest.fixture
    def error_app(self):
        """Create a minimal Flask app with routes that raise specific exceptions."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'

        @app.route('/raise-validation-error', methods=['POST'])
        @handle_errors
        def raise_validation_error():
            raise ValidationError("Invalid input data")

        @app.route('/raise-authentication-error', methods=['POST'])
        @handle_errors
        def raise_authentication_error():
            raise AuthenticationError("Invalid credentials")

        @app.route('/raise-rate-limit', methods=['POST'])
        @handle_errors
        def raise_rate_limit():
            raise RateLimitExceeded("Daily limit exceeded")

        @app.route('/raise-timeout-error', methods=['POST'])
        @handle_errors
        def raise_timeout_error():
            raise TimeoutError("Connection timed out")

        @app.route('/raise-generic-exception', methods=['POST'])
        @handle_errors
        def raise_generic_exception():
            raise Exception("Something went wrong")

        return app

    @pytest.fixture
    def error_client(self, error_app):
        """Create test client for the error app."""
        return error_app.test_client()

    def test_validation_error_returns_400(self, error_client):
        """ValidationError should map to HTTP 400."""
        response = error_client.post('/raise-validation-error')
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid input data" in data["error"]

    def test_authentication_error_returns_401(self, error_client):
        """AuthenticationError should map to HTTP 401."""
        response = error_client.post('/raise-authentication-error')
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid credentials" in data["error"]

    def test_rate_limit_exceeded_returns_429(self, error_client):
        """RateLimitExceeded should map to HTTP 429."""
        response = error_client.post('/raise-rate-limit')
        assert response.status_code == 429
        data = response.get_json()
        assert "error" in data
        assert "Daily limit exceeded" in data["error"]

    def test_timeout_error_returns_503(self, error_client):
        """TimeoutError should map to HTTP 503."""
        response = error_client.post('/raise-timeout-error')
        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data

    def test_generic_exception_returns_500(self, error_client):
        """Generic Exception should map to HTTP 500."""
        response = error_client.post('/raise-generic-exception')
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data


if __name__ == '__main__':
    pytest.main([__file__]) 