"""Shared authentication utilities for PDN application."""

from functools import wraps
from flask import session, jsonify


def require_auth(f):
    """Decorator that requires an authenticated session.
    
    Checks for either 'user_email' (binat/relationships) or 'email' (diagnose)
    in the Flask session. Returns 401 if neither is present.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_email') and not session.get('email'):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return wrapper
