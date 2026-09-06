from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from app.main import create_app

app_instance = create_app()

if __name__ == '__main__':
    app_instance.run(debug=True, host='0.0.0.0', port=8001)
