"""
PDN Chat AI Routes - Flask routes for AI-powered chat interface.
Handles user authentication, chat messaging, and 21-day plan generation.
"""

import threading
import uuid
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, render_template, jsonify, session

from .binat_agents.pdn_agent import PDNAgent
from .logger import setup_logger
from .user_manager import get_user_manager
from ..utils.auth import require_auth
from ..utils.conversation_stats import conversation_stats
from ..utils.user_history_service import UserHistoryPayload, UserHistoryService

logger = setup_logger()
_pdn_agent = None
_agent_lock = threading.Lock()
_history_service = UserHistoryService()

# Track active chat sessions
chat_sessions = {}  # session_id -> {email, user_id, login_time}
MAX_CHAT_SESSIONS = 500  # Prevent unbounded growth


def _cleanup_stale_sessions():
    """Remove sessions older than 4 hours to prevent memory leaks."""
    now = datetime.now()
    stale = [sid for sid, info in chat_sessions.items()
             if (now - info.get('login_time', now)).total_seconds() > 14400]
    for sid in stale:
        del chat_sessions[sid]


# --- Custom exceptions for differentiated error handling ---

class ValidationError(Exception):
    """Raised for invalid input (400)."""
    pass


class AuthenticationError(Exception):
    """Raised for auth failures (401)."""
    pass


class RateLimitExceeded(Exception):
    """Raised when user hits rate/daily limits (429)."""
    pass


def get_agent_instance():
    """Get or create the single PDN agent instance"""
    global _pdn_agent
    if _pdn_agent is None:
        with _agent_lock:
            if _pdn_agent is None:
                _pdn_agent = PDNAgent()
                logger.info("Created new PDNAgent instance")
    return _pdn_agent

def handle_errors(f):
    """Decorator with differentiated error handling by exception type."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning("Validation error in %s: %s", f.__name__, e)
            return jsonify({"error": str(e)}), 400
        except AuthenticationError as e:
            logger.warning("Auth error in %s: %s", f.__name__, e)
            return jsonify({"success": False, "error": str(e)}), 401
        except RateLimitExceeded as e:
            logger.info("Rate limit in %s: %s", f.__name__, e)
            return jsonify({"error": str(e)}), 429
        except (TimeoutError, ConnectionError) as e:
            logger.error("Network error in %s: %s", f.__name__, e)
            return jsonify({"error": "שגיאת תקשורת עם שרת ה-AI. אנא נסה שוב."}), 503
        except Exception as e:
            logger.error("Unexpected error in %s: %s", f.__name__, e, exc_info=True)
            return jsonify({"error": "שגיאה פנימית. אנא נסה שוב."}), 500
    return wrapper

pdn_chat_ai_bp = Blueprint('pdn_chat_ai', __name__, template_folder='templates', static_folder='../static')

@pdn_chat_ai_bp.route('/')
def chat():
    """Binat Chat AI login endpoint"""
    return render_template("binat_login.html")

@pdn_chat_ai_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """Handle user login with email and password verification"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user_data = get_user_manager().get_user(email)
    if user_data and get_user_manager().verify_password(email, password):
        # Server-side enforcement: terms must be accepted
        if not data.get('terms_accepted'):
            logger.warning("Login blocked — terms not accepted for: %s", email)
            return jsonify({"success": False, "error": "יש לאשר את תנאי השימוש כדי להמשיך"}), 403

        user_id = str(uuid.uuid4())
        daily_conversation_limit = user_data.get('daily_conversation_limit', 15)
        access_days = user_data.get('access_days', 0)
        created_at = user_data.get('created_at', '')

        # Check days-based access expiry before allowing login
        if access_days > 0 and created_at:
            try:
                created_dt = datetime.strptime(created_at[:10], '%Y-%m-%d')
                days_elapsed = (datetime.now() - created_dt).days
                if days_elapsed >= access_days:
                    logger.info("Access expired for %s (%d days elapsed, limit %d)", email, days_elapsed, access_days)
                    return jsonify({"success": False, "error": "תקופת הגישה שלך הסתיימה. אנא פנה לתמיכה."}), 403
            except (ValueError, TypeError):
                pass  # If date is unparseable, allow login

        session.permanent = True
        session.update({
            'user_id': user_id,
            'user_email': email,
            'user_name': user_data['name'],
            'pdn_code': user_data['pdn_code'],
            'daily_conversation_limit': daily_conversation_limit,
            'access_days': access_days,
            'created_at': created_at,
        })
        # Track active session (with cleanup to prevent unbounded growth)
        _cleanup_stale_sessions()
        if len(chat_sessions) >= MAX_CHAT_SESSIONS:
            # Remove oldest session
            oldest = min(chat_sessions, key=lambda k: chat_sessions[k].get('login_time', datetime.min))
            del chat_sessions[oldest]
        chat_sessions[session.sid] = {
            "email": email,
            "user_id": user_id,
            "login_time": datetime.now()
        }

        # Load persisted conversation history for cross-session continuity
        history_payload = _history_service.load_user_history(email)
        session['user_history'] = history_payload.to_dict() if history_payload else None

        # Audit: record terms acceptance timestamp in user profile
        get_user_manager().record_terms_acceptance(email)

        logger.info("User %s logged in successfully", email)
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user_id": user_id,
            "user_name": user_data['name'],
            "pdn_code": user_data['pdn_code'],
            "daily_conversation_limit": daily_conversation_limit,
            "access_days": access_days,
        })

    logger.warning("Failed login attempt for email: %s", email)
    return jsonify({"success": False, "error": "Invalid email or password"}), 401

@pdn_chat_ai_bp.route('/logout', methods=['POST'])
@handle_errors
def logout():
    """Handle user logout — save conversation history before clearing session."""
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    
    # Persist conversation history via the agent's public API
    if user_name and user_email:
        agent = get_agent_instance()
        agent.persist_session(user_name, user_email)
        logger.info("Saved conversation history for %s on logout", user_email)
    
    # Remove from active sessions
    chat_sessions.pop(session.sid, None)
    
    session.clear()
    logger.info("User %s logged out successfully (history preserved)", user_email)
    return jsonify({"success": True, "message": "Logout successful"})

@pdn_chat_ai_bp.route('/binat')
def chat_interface():
    """Chat interface endpoint - accessed after login"""
    # If no session, redirect to login instead of serving a broken page
    if not session.get('user_email'):
        from flask import redirect, url_for
        return redirect(url_for('pdn_chat_ai.chat'))
    return render_template(
        "chat.html",
        welcome_message="ברוך הבא לבינת קוד המקור ",
        user_name=session.get('user_name') or request.args.get('user_name', 'Anonymous'),
        user_id=session.get('user_id') or request.args.get('user_id', ''),
        pdn_code=session.get('pdn_code') or request.args.get('pdn_code', ''),
        include_menu=True
    )

@pdn_chat_ai_bp.route('/chat', methods=['POST'])
@require_auth
@handle_errors
def chat_with_binat():
    """Handle chat messages with improved AI responses"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate message length
    message = data.get('message', '').strip()
    if not message:
        raise ValidationError("Message cannot be empty")
    if len(message) > 5000:
        raise ValidationError("Message too long (max 5000 characters)")

    # Track conversation — prefer session email, fall back to POST body email
    user_email = session.get('user_email') or data.get('email', '')
    if user_email:
        conversation_stats.increment_conversation(user_email)

    # Get daily_conversation_limit from session or use default
    daily_conversation_limit = session.get('daily_conversation_limit', 15)

    agent = get_agent_instance()

    # Register email mapping for history persistence (display name may be Hebrew)
    chat_user_name = data.get('user_name', 'Anonymous')
    if user_email and chat_user_name:
        agent.register_user_email(chat_user_name, user_email)

    # Inject persisted history into agent context (once per session)
    user_history_data = session.pop('user_history', None)
    if user_history_data:
        payload = UserHistoryPayload.from_dict(user_history_data)
        # Seed the agent's in-memory summary with persisted history + session marker
        last_date = payload.metadata.get('last_session_date', payload.updated_at[:10])
        session_marker = f"\n--- שיחה חדשה ({datetime.now().strftime('%d.%m.%Y')}) | שיחה קודמת: {last_date} ---"
        agent.conversation_history[chat_user_name].summary = payload.summary + session_marker

    return jsonify({
        "response": agent.chat_with_binat(
            message,
            chat_user_name,
            data.get('pdn_code', ''),
            daily_conversation_limit=daily_conversation_limit
        ),
        "timestamp": datetime.now().isoformat()
    })

@pdn_chat_ai_bp.route('/21-day-plan', methods=['POST'])
@require_auth
@handle_errors
def build_21_transformation_plan():
    """Handle 21-day transformation plan requests"""
    data = request.get_json()
    goal = data.get('goal', '').strip()
    user_name = data.get('user_name', '')
    pdn_code = data.get('pdn_code', '')

    if not goal:
        return jsonify({"error": "Goal is required"}), 400

    # Track conversation — prefer session email, fall back to POST body email
    user_email = session.get('user_email') or data.get('email', '')
    if user_email:
        conversation_stats.increment_conversation(user_email)

    # Get daily_conversation_limit from session or use default
    daily_conversation_limit = session.get('daily_conversation_limit', 15)

    agent = get_agent_instance()

    return jsonify({
        "response": agent.build_21_transformation_plan(goal, user_name, pdn_code, daily_conversation_limit),
        "timestamp": datetime.now().isoformat()
    })

@pdn_chat_ai_bp.route('/daily-training', methods=['POST'])
@require_auth
@handle_errors
def daily_training():
    """Handle daily training requests"""
    data = request.get_json()
    task = data.get('task', '').strip()
    user_name = data.get('user_name', 'Anonymous')
    pdn_code = data.get('pdn_code', '')

    if not task:
        return jsonify({"error": "Task is required"}), 400

    # Track conversation — prefer session email, fall back to POST body email
    user_email = session.get('user_email') or data.get('email', '')
    if user_email:
        conversation_stats.increment_conversation(user_email)

    # Get daily_conversation_limit from session or use default
    daily_conversation_limit = session.get('daily_conversation_limit', 15)

    agent = get_agent_instance()

    return jsonify({
        "response": agent.daily_training(
            user_name,
            pdn_code,
            task,
            daily_conversation_limit
        ),
        "timestamp": datetime.now().isoformat()
    })
