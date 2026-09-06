import json
import logging
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request

from app.pdn_admin import pdn_admin_bp, audio_bp
from app.pdn_chat_ai import pdn_chat_ai_bp
from app.pdn_diagnose import pdn_diagnose_bp
from app.neo import neo_bp
from app.pdn_relationships import pdn_relationships_bp
from flask_session import Session
from app.utils.memory_monitor import start_memory_monitoring

def create_app():
    """Application factory pattern for Flask app creation"""
    app = Flask(__name__)

    # Configuration
    app.config.update(
        SECRET_KEY=os.environ['SECRET_KEY'],  # Must be set — no default
        SESSION_TYPE='filesystem',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max request size
    )

    Session(app)

    # Setup logging
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler('logs/app.log')]
    )

    logger = logging.getLogger(__name__)

    # Load questions
    questions_path = Path(__file__).parent / "data" / "questions.json"
    try:
        app.config['QUESTIONS_FILE'] = json.loads(questions_path.read_text(encoding="utf-8"))
        logger.debug(f"Loaded {len(app.config['QUESTIONS_FILE'].get('phases', {}))} question phases")
    except Exception as e:
        logger.error(f"Failed to load questions: {e}")
        app.config['QUESTIONS_FILE'] = {}

    # Register blueprints
    for bp, prefix in [
        (pdn_diagnose_bp, '/pdn-diagnose'),
        (pdn_admin_bp, '/pdn-admin'),
        (audio_bp, '/pdn-admin'),
        (pdn_chat_ai_bp, '/pdn-binat'),
        (neo_bp, '/neo'),
        (pdn_relationships_bp, '/pdn-relationships')
    ]:
        app.register_blueprint(bp, url_prefix=prefix)

    # Production monitoring
    if os.getenv('FLASK_ENV') == 'production':
        start_memory_monitoring()

    # Root route
    @app.route('/')
    def root():
        return {
            "message": "Welcome to PDN Flask Application 1.0",
            "modules": [
                "/pdn-diagnose - Personal development interaction",
                "/pdn-admin - Admin dashboard and monitoring",
                "/pdn-binat - AI chat assistance",
                "/neo - Neo P.D.N Center",
                "/pdn-relationships - Relationship advisor"
            ]
        }

    # Request/response logging (sanitized — no query params)
    @app.before_request
    def log_request():
        logger.info(f"{request.method} {request.path}")

    @app.after_request
    def log_response(response):
        logger.info(f"Status: {response.status_code}")
        return response

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8001)
