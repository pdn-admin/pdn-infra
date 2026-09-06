"""
PDN Relationships Routes - Flask routes for relationship advisor chatbot.
Handles user authentication, chat messaging, and session management
for the relationship advice module.
"""

import threading
import uuid
import logging
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, render_template, jsonify, session

from .constants import PDN_CODES, RelationshipType
from .agents.relationship_agent import RelationshipAgent
from ..pdn_chat_ai.user_manager import get_user_manager
from ..utils.auth import require_auth
from ..utils.conversation_stats import conversation_stats
from ..utils.user_history_service import UserHistoryPayload, UserHistoryService

logger = logging.getLogger(__name__)

_relationship_agent = None
_relationship_agent_lock = threading.Lock()
_history_service = UserHistoryService()


def get_relationship_agent():
    """Get or create the single RelationshipAgent instance.
    
    Uses Anthropic (Sonnet for chat, Haiku for summarization) — same as binat.
    """
    global _relationship_agent
    if _relationship_agent is None:
        with _relationship_agent_lock:
            if _relationship_agent is None:
                from .agents.base_pdn_agent import BaseAgentConfig
                config = BaseAgentConfig(llm_provider='anthropic')
                _relationship_agent = RelationshipAgent(config=config)
                logger.info("Created new RelationshipAgent instance")
    return _relationship_agent


def handle_errors(f):
    """Decorator with differentiated error handling by exception type."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning("Validation error in %s: %s", f.__name__, e)
            return jsonify({"error": str(e)}), 400
        except (TimeoutError, ConnectionError) as e:
            logger.error("Network error in %s: %s", f.__name__, e)
            return jsonify({"error": "שגיאת תקשורת עם שרת ה-AI. אנא נסה שוב."}), 503
        except Exception as e:
            logger.error("Unexpected error in %s: %s", f.__name__, e, exc_info=True)
            return jsonify({"error": "שגיאה פנימית. אנא נסה שוב."}), 500
    return wrapper


pdn_relationships_bp = Blueprint(
    'pdn_relationships',
    __name__,
    template_folder='templates',
    static_folder='../static',
)


@pdn_relationships_bp.route('/')
def login_page():
    """Render the relationship advisor login page."""
    return render_template("relationship_login.html")


@pdn_relationships_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """Authenticate user and store relationship context in session.

    Request body: {email, password, partner_code, relationship_type}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    partner_code = data.get('partner_code', '').strip().lower()
    relationship_type = data.get('relationship_type', '').strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if partner_code not in PDN_CODES:
        return jsonify({"error": f"Invalid partner code: {partner_code}"}), 400

    valid_relationship_types = [rt.value for rt in RelationshipType]
    if relationship_type not in valid_relationship_types:
        return jsonify({"error": f"Invalid relationship type: {relationship_type}"}), 400

    user_data = get_user_manager().get_user(email)
    if user_data and get_user_manager().verify_password(email, password):
        user_id = str(uuid.uuid4())
        daily_conversation_limit = user_data.get('daily_conversation_limit', 15)

        session.permanent = True
        session.update({
            'user_id': user_id,
            'user_email': email,
            'user_name': user_data['name'],
            'pdn_code': user_data['pdn_code'],
            'partner_code': partner_code,
            'relationship_type': relationship_type,
            'daily_conversation_limit': daily_conversation_limit,
        })

        # Load persisted conversation history for cross-session continuity
        history_payload = _history_service.load_user_history(email)
        session['user_history'] = history_payload.to_dict() if history_payload else None

        logger.info("User %s logged in to relationship advisor", email)
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user_id": user_id,
            "user_name": user_data['name'],
            "pdn_code": user_data['pdn_code'],
            "partner_code": partner_code,
            "relationship_type": relationship_type,
            "daily_conversation_limit": daily_conversation_limit,
        })

    logger.warning("Failed login attempt for email: %s", email)
    return jsonify({"success": False, "error": "Invalid email or password"}), 401


@pdn_relationships_bp.route('/chat', methods=['POST'])
@require_auth
@handle_errors
def chat():
    """Handle chat messages for relationship advice.

    Request body: {message, user_name, pdn_code, partner_code, relationship_type}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    message = data.get('message', '').strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(message) > 5000:
        return jsonify({"error": "Message too long (max 5000 characters)"}), 400

    user_name = data.get('user_name', '')
    user_code = data.get('pdn_code', '')
    partner_code = data.get('partner_code', '')
    relationship_type = data.get('relationship_type', '')

    # Track conversation stats
    user_email = session.get('user_email') or data.get('email', '')
    if user_email:
        conversation_stats.increment_conversation(user_email)

    # Get agent instance
    agent = get_relationship_agent()

    # Register email mapping for history persistence
    if user_email and user_name:
        agent.register_user_email(user_name, user_email)

    # Inject persisted history (once per session via session.pop)
    user_history_data = session.pop('user_history', None)
    if user_history_data:
        payload = UserHistoryPayload.from_dict(user_history_data)
        last_date = payload.metadata.get('last_session_date', payload.updated_at[:10])
        session_marker = f"\n--- שיחה חדשה ({datetime.now().strftime('%d.%m.%Y')}) | שיחה קודמת: {last_date} ---"
        agent.conversation_history[user_name].summary = payload.summary + session_marker

    # Get daily conversation limit from session
    daily_limit = session.get('daily_conversation_limit', 15)

    # Call agent.chat() with all parameters
    response_text = agent.chat(
        message=message,
        user_name=user_name,
        user_code=user_code,
        partner_code=partner_code,
        relationship_type=relationship_type,
        daily_conversation_limit=daily_limit,
    )

    return jsonify({
        "response": response_text,
        "timestamp": datetime.now().isoformat(),
    })


@pdn_relationships_bp.route('/logout', methods=['POST'])
@require_auth
@handle_errors
def logout():
    """Save conversation history and clear session."""
    user_email = session.get('user_email')
    user_name = session.get('user_name')

    # Persist conversation history via the agent's public API
    if user_name and user_email:
        agent = get_relationship_agent()
        agent.persist_session(user_name, user_email)
        logger.info("Saved conversation history for %s on logout", user_email)

    session.clear()
    logger.info("User %s logged out from relationship advisor", user_email)
    return jsonify({"success": True, "message": "Logout successful"})


@pdn_relationships_bp.route('/chat-page')
@require_auth
def chat_page():
    """Render the relationship chat interface with session context."""
    return render_template(
        "relationship_chat.html",
        user_name=session.get('user_name', ''),
        pdn_code=session.get('pdn_code', ''),
        partner_code=session.get('partner_code', ''),
        relationship_type=session.get('relationship_type', ''),
    )
