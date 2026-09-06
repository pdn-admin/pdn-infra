"""Shared fixtures for PDN Chat backend tests."""

import os
import sys
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env(monkeypatch):
    """Set minimal environment variables for testing."""
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-anthropic-key')
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('FLASK_ENV', 'testing')
