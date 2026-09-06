# PDN Center Application

## Overview
PDN Center is a comprehensive Flask application designed for psychological assessment and diagnosis through structured questionnaires, AI-powered chat interactions, and administrative management. The application is organized into three main modules that work together to provide a complete assessment platform.

## Key Features
- **Structured Questionnaire System**: 65-question psychological assessment with voice recording capabilities
- **AI-Powered Chat Interface**: Intelligent conversation system with context awareness
- **45-Day Transformation Plans**: Personalized transformation programs based on user goals and PDN codes
- **Administrative Dashboard**: Complete user management, data visualization, and system administration
- **Voice Analysis**: Audio recording and analysis for enhanced assessment
- **Report Generation**: Automated PDF and JSON report generation
- **Email Integration**: Automated report delivery to users
- **Data Export**: CSV export functionality for data analysis

## Architecture

### Core Modules
- **`pdn_diagnose`**: User questionnaire, answer submission, and PDN code calculation
- **`pdn_chat_ai`**: AI-powered chat interface with PDN-specific agents
- **`pdn_admin`**: Administrative dashboard for user and system management

### Technology Stack
- **Backend**: Python 3.9+, Flask 3.1.1, FastAPI 0.115.6
- **Frontend**: HTML5, JavaScript (ES6+), Tailwind CSS 3.4.0
- **AI/ML**: OpenAI GPT-4, Anthropic Claude, LangChain 0.3+ for AI-powered conversations
- **Database**: File-based session storage
- **PDF Generation**: HTML2PDF.js
- **Audio Processing**: Web Audio API, WAV format support

## Installation & Setup

### Prerequisites
- Python 3.9 or higher
- Node.js 16+ (for Tailwind CSS compilation)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/Tomer007/pdn_chat.git
cd pdn_chat
```

### 2. Python Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Node.js Dependencies (for CSS compilation)
```bash
# Install Node.js dependencies
npm install

# Build CSS (development)
npm run build:css

# Build CSS (production)
npm run build:css:prod
```

### 4. Environment Configuration
Create a `.env` file in the root directory:
```env
# Admin Configuration
ADMIN_PASSWORD=your_secure_password

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Database Configuration

# Email Configuration (optional)
SMTP_SERVER=your_smtp_server
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_password
```

### 5. Run the Application
```bash
# Quick start (recommended)
./run_local.sh

# Or manually:
source venv/bin/activate
python -m flask run --port 5000

# Production mode
gunicorn app.main:app
```

## Application Access

### Main Endpoints
- **Home**: `http://127.0.0.1:8001/`
- **User Assessment**: `http://127.0.0.1:8001/pdn-diagnose/`
- **AI Chat Interface**: `http://127.0.0.1:8001/pdn-binat/`
- **Admin Login**: `http://127.0.0.1:8001/pdn-admin/`
- **Admin Dashboard**: `http://127.0.0.1:8001/pdn-admin/dashboard`

## API Documentation

### PDN Diagnose Module (`/pdn-diagnose`)
**User Interface:**
- `GET /pdn-diagnose/` - User login page
- `GET /pdn-diagnose/user_info` - User information form
- `POST /pdn-diagnose/user_info` - Save user information
- `POST /pdn-diagnose/login` - User authentication

**Questionnaire System:**
- `GET /pdn-diagnose/questionnaire/<question_number>` - Get specific question
- `POST /pdn-diagnose/answer` - Submit question answer
- `POST /pdn-diagnose/complete_questionnaire` - Complete assessment

**Reports & Results:**
- `GET /pdn-diagnose/pdn_report` - View PDN report
- `GET /pdn-diagnose/get_report_data` - Get report data (JSON)
- `POST /pdn-diagnose/send_email` - Send report via email

### PDN Binat Module (`/pdn-binat`)
**Chat Interface:**
- `GET /pdn-binat/` - Chat interface page
- `POST /pdn-binat/chat` - Send chat message
- `POST /pdn-binat/21-day-plan` - Generate 21-day transformation plan
- `POST /pdn-binat/daily-training` - Daily training requests
- `POST /pdn-binat/login` - User authentication
- `POST /pdn-binat/logout` - User logout

### PDN Admin Module (`/pdn-admin`)
**Authentication:**
- `GET /pdn-admin/` - Admin login page
- `POST /pdn-admin/login` - Admin authentication
- `GET /pdn-admin/logout` - Admin logout

**Data Management:**
- `GET /pdn-admin/metadata/csv` - Get user metadata
- `GET /pdn-admin/download/csv` - Download CSV data
- `GET /pdn-admin/user/questionnaire/<email>` - Get user questionnaire
- `GET /pdn-admin/user/voice/<email>` - Get voice recordings
- `PUT /pdn-admin/user/diagnose/<email>` - Update diagnosis
- `POST /pdn-admin/user/send_email/<email>` - Send email to user
- `POST /pdn-admin/user/recalculate_pdn/<email>` - Recalculate PDN code

**Audio Management:**
- `GET /pdn-admin/audio/<path:file_path>` - Serve audio files
- `POST /pdn-admin/api/save-audio` - Save audio file

## Questionnaire System

### Question Structure
- **Total Questions**: 65 questions across 6 sections (A-F)
- **Question Types**:
  - Questions 1-26: Single-choice questions
  - Questions 27-65: Ranking and scale questions
- **Voice Recording**: Questions 1 and 2 support voice recording
- **Progress Tracking**: Real-time progress indication

### PDN Code Calculation
- Automated calculation based on questionnaire responses
- Multiple validation layers for accuracy
- Support for manual recalculation by administrators

## AI Chat Features

### AI Chat System
- **PDN-Specific Agents**: Dynamic prompt loading based on user's PDN code
- **Conversation History**: Persistent conversation storage per user
- **21-Day Plans**: Personalized transformation plan generation
- **Multi-Language Support**: Hebrew and English responses

### Chat Capabilities
- **Real-time Messaging**: WebSocket-based communication
- **Voice Integration**: Audio message support
- **History Management**: Persistent conversation storage
- **Settings Management**: Customizable chat parameters

### 45-Day Transformation Plans
- **Personalized Plans**: Custom transformation programs based on user goals and PDN codes
- **Interactive Modal**: User-friendly interface for goal setting and success definition
- **A7Agent Integration**: Specialized AI agent for plan generation using A7 PDN code
- **Structured Format**: Daily plans with mindset focus, practice, and reflection components
- **Hebrew Language Support**: Full RTL support and Hebrew interface
- **Enter Key Support**: Quick form submission with keyboard shortcuts
- **Error Handling**: Comprehensive error management and fallback responses

## Admin Dashboard Features

### User Management
- **User Overview**: Complete user data visualization
- **Search & Filter**: Advanced filtering capabilities
- **Data Export**: CSV export functionality
- **Visual Indicators**: Color-coded status indicators

### Audio Management
- **Voice Recording Playback**: Listen to user voice recordings
- **File Management**: Organize and manage audio files
- **Quality Control**: Audio validation and processing

### System Administration
- **Session Management**: Monitor active sessions
- **Log Analysis**: Comprehensive logging system
- **Performance Monitoring**: System health indicators

## Security Features

### Authentication
- **Admin Authentication**: Secure admin login system
- **Session Management**: File-based session storage
- **Password Protection**: Configurable admin passwords

### Data Protection
- **Input Validation**: Comprehensive data validation
- **File Upload Security**: Secure audio file handling
- **Error Handling**: Graceful error management

## Development

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_pdn_calculator.py

# Run with coverage
pytest --cov=app tests/
```

### CSS Development
```bash
# Watch mode for CSS changes
npm run build:css

# Production CSS build
npm run build:css:prod
```

### Code Quality
- **Linting**: Python code follows PEP 8 standards
- **Type Hints**: Comprehensive type annotations
- **Documentation**: Inline code documentation
- **Error Handling**: Robust error management

## Deployment

### Production Configuration
- **WSGI Server**: Gunicorn with multiple workers
- **Static Files**: Served via Flask static file handling
- **Database**: File-based session storage
- **Logging**: Structured logging with rotation

### Environment Variables
```env
# Required
ADMIN_PASSWORD=secure_password
OPENAI_API_KEY=your_api_key

# Optional
FLASK_ENV=production
LOG_LEVEL=INFO
```

## Troubleshooting

### Common Issues

**1. LangChain Import Errors**
```bash
# If you encounter ImportError with langchain packages
python3 -m pip install --upgrade langchain-core langchain-anthropic langchain-openai langchain langchain-community
```

**2. Import Errors**
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**3. Static File Issues**
```bash
# Rebuild CSS
npm run build:css:prod
```

**4. Database Issues**
```bash
# Clear session data if corrupted
rm -rf flask_session/
# Restart application
```

**5. Audio Upload Issues**
- Check file permissions in `saved_results/`
- Verify audio format (WAV supported)
- Check browser console for JavaScript errors

### Dependency Compatibility

The application requires compatible versions of LangChain packages:
- `langchain>=0.3.27`
- `langchain-core>=0.3.80`
- `langchain-openai>=0.3.35`
- `langchain-anthropic>=0.3.22`
- `langsmith>=0.4.37`

If you encounter version conflicts, upgrade all LangChain packages together:
```bash
python3 -m pip install --upgrade langchain langchain-core langchain-openai langchain-anthropic langchain-community langsmithSS
npm run build:css:prod
```



### Log Analysis
```bash
# View application logs
tail -f logs/app.log

# View specific error logs
grep "ERROR" logs/app.log
```

## Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and test thoroughly
4. Commit changes: `git commit -m "Add new feature"`
5. Push to branch: `git push origin feature/new-feature`
6. Create a Pull Request

### Code Standards
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add type hints for all functions
- Include docstrings for classes and functions
- Write tests for new functionality

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Support
For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details

## Changelog

### Version 2.7.1-20260606 (Latest)
- ✅ **NEW**: Admin Metrics Dashboard — KPIs, code distribution, daily volume, match/mismatch chart
- ✅ **NEW**: PDN code distribution grouped by trait (A/T/P/E) and energy (D/S/F)
- ✅ **NEW**: Code match/mismatch donut chart with detailed breakdown
- ✅ **NEW**: "Needs verification" metric with clickable filter
- ✅ **NEW**: Clickable "אימות" badge shows reason: "הפער בין הציונים קטן מ-2 נקודות"
- ✅ **NEW**: Date range filters (7 days, 30 days, year, all)
- ✅ **NEW**: Send calculation report via email from recalculation modal
- ✅ **NEW**: Send algorithm report via email from dashboard
- ✅ **NEW**: Search by name/email in data table
- ✅ **NEW**: PDN algorithm HTML report (`docs/pdn_algorithm_report.html`)
- ✅ **NEW**: Admin recalculate guide (`docs/admin_recalculate_guide.html`)
- ✅ **NEW**: `run_local.sh` script for local development
- ✅ **NEW**: Render log review steering file (`.kiro/steering/render-log-review.md`)
- ✅ Mobile UX improvements — hidden title, centered buttons, question-first layout
- ✅ Session expired modal (401) with Hebrew re-login prompt
- ✅ Network error retry with Hebrew messages
- ✅ Removed disclaimer from diagnose login page
- ✅ Second recording mandatory in production
- ✅ Question text in black, ranking items bolder
- ✅ Completion screen: full text + "לאתר PDN CENTER" button with subtitle
- ✅ Login button: dark gold gradient with white text
- ✅ Time remaining display completely removed
- ✅ Question 1 rewording + question mark on Q28
- ✅ `needs_verification` calculated and displayed in admin
- ✅ Removed unused files: `RELEASE_NOTES.md`, `admin-dashboard.css/js`, `P-10.pdf`, flask_session
- ✅ 19 new tests for metrics, email, and distribution logic

### Version 2.6.0 (2025-05-19)
- ✅ Complete coupon management system
- ✅ Unified login (password or coupon code)
- ✅ Coupon display in questionnaire and admin table
- ✅ Refresh button in coupon management widget
- ✅ Security improvements
- ✅ Log cleanup

### Version 1.1.0
- ✅ 45-Day Transformation Plan feature
- ✅ Complete admin dashboard redesign
- ✅ Enhanced voice recording
- ✅ PDN-specific AI agents
- ✅ PDF and JSON report generation
- ✅ Comprehensive test coverage

---

**Note**: This application is designed for psychological assessment purposes. Ensure compliance with relevant data protection regulations (GDPR, HIPAA, etc.) when handling personal data.