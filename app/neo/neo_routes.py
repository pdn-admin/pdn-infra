"""
Neo P.D.N Center Routes
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import uuid
import json
import base64
import io
from pathlib import Path
from openai import OpenAI
import os

# Create blueprint for neo module
neo_bp = Blueprint('neo', __name__, 
                   template_folder='templates',
                   static_folder='../static')

@neo_bp.route('/')
def index():
    """Neo P.D.N Center home page - redirects to login"""
    return render_template('neo_login.html')

@neo_bp.route('/login')
def login():
    """Neo P.D.N Center login page"""
    return render_template('neo_login.html')

@neo_bp.route('/analysis')
def analysis():
    """Neo analysis page"""
    # Load insurance data
    insurance_file = Path(__file__).parent / 'data' / 'products.json'
    with open(insurance_file, 'r', encoding='utf-8') as f:
        insurance_data = json.load(f)
    
    return render_template('analysis.html', insurance_data=insurance_data)

@neo_bp.route('/logout')
def logout():
    """Handle logout - clear session and redirect to login page"""
    # Return a page that clears localStorage before redirecting
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logging out...</title>
        <script>
            // Clear Neo-related localStorage items
            localStorage.removeItem('neo_username');
            localStorage.removeItem('neo_user_id');
            localStorage.removeItem('neo_pdn_code');
            localStorage.removeItem('neo_pdn_company_form');
            
            // Redirect to login page
            window.location.href = '/neo/login';
        </script>
    </head>
    <body>
        <p>Logging out...</p>
    </body>
    </html>
    """

@neo_bp.route('/login', methods=['POST'])
def login_post():
    """Handle Neo login"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        # Simple validation - in real app, check against database
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'אימייל וסיסמה נדרשים'
            }), 400
        
        # For demo purposes, accept any email/password combination
        # In real app, validate against user database
        user_name = email.split('@')[0]  # Extract name from email
        user_id = str(uuid.uuid4())
        pdn_code = "E5"  # Default PDN code for demo
        
        return jsonify({
            'success': True,
            'user_name': user_name,
            'user_id': user_id,
            'pdn_code': pdn_code,
            'message': 'התחברות בוצעה בהצלחה'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'שגיאה בשרת'
        }), 500

@neo_bp.route('/analyze', methods=['POST'])
def analyze():
    """Handle company data analysis with voice transcription"""
    try:
        data = request.get_json()
        
        # Validate data
        if not data or 'company' not in data:
            return jsonify({
                'success': False,
                'error': 'חסרים נתוני חברה'
            }), 400
        
        company_name = data['company'].get('name', '')
        company_about = data['company'].get('about', '')
        company_url = data['company'].get('url', '')
        products = data.get('products', [])
        voice_recording = data.get('voiceRecording')
        
        # Validate voice recording
        if not voice_recording:
            return jsonify({
                'success': False,
                'error': 'חסרה הקלטה קולית'
            }), 400
        
        # Handle demo sample or real recording
        if voice_recording.get('isDemoSample'):
            # Use demo sample text directly
            transcribed_text = voice_recording.get('transcribedText', '')
            if not transcribed_text:
                return jsonify({
                    'success': False,
                    'error': 'חסר טקסט בדגימה'
                }), 400
        else:
            # Transcribe real voice recording using OpenAI Whisper
            if not voice_recording.get('base64'):
                return jsonify({
                    'success': False,
                    'error': 'חסרה הקלטה קולית'
                }), 400
            
            try:
                # Decode base64 audio
                audio_data = base64.b64decode(voice_recording['base64'])
                audio_file = io.BytesIO(audio_data)
                audio_file.name = 'recording.wav'
                
                # Initialize OpenAI client
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                # Transcribe using Whisper
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="he"  # Hebrew
                )
                
                transcribed_text = transcript.text
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'שגיאה בתמלול ההקלטה: {str(e)}'
                }), 500
        
        # Analyze using NeoAgent
        try:
            from app.neo.neo_agents import get_neo_agent
            neo_agent = get_neo_agent()
            
            # Prepare company data for context
            company_context = {
                'name': company_name,
                'about': company_about,
                'url': company_url,
                'products': products
            }
            
            analysis_result = neo_agent.analyze_customer_code(transcribed_text, company_context)
            
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'שגיאת אימות: {str(e)}'
            }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'שגיאה באנליזה: {str(e)}'
            }), 500
        
        analysis_id = str(uuid.uuid4())
        
        return jsonify({
            'success': True,
            'analysis_id': analysis_id,
            'message': 'הנתונים נשלחו בהצלחה לאנליזה',
            'company_name': company_name,
            'product_count': len(products),
            'transcription': transcribed_text,
            'analysis': analysis_result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'שגיאה בשרת: {str(e)}'
        }), 500

