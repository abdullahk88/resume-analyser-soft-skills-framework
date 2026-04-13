import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'mocka-ai-super-secret-key-change-in-prod')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    LLAMA_MODEL = "llama-3.1-8b-instant"   # fast & available on Groq as of 2026

    MYSQL_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'resume_analyzer')
    }

    # Flask-Mail config (use Gmail App Password)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')   # your Gmail
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')   # Gmail App Password

    # Google OAuth Client ID (from Google Cloud Console)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')

    UPLOAD_FOLDER = 'recorded_answers'
