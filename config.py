import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/event_management')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24 hours 
    
    # Add MongoDB client options
    MONGO_OPTIONS = {
        'serverSelectionTimeoutMS': 5000,
        'connectTimeoutMS': 10000,
        'socketTimeoutMS': 10000
    }
    
    # Mailgun Configuration
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_FROM_EMAIL = os.getenv('MAILGUN_FROM_EMAIL', 'noreply@aup.events')
    
    # Environment check
    ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = ENV == 'development'
    
    # Add secret key for sessions (required for CSRF)
    SECRET_KEY = os.getenv('SECRET_KEY', 'session_key_aupevents')
    
    # Event approval configuration
    EVENT_APPROVAL_REQUIRED = os.getenv('EVENT_APPROVAL_REQUIRED', 'True').lower() in ('true', '1', 't')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', '')
    
    # API base URL for direct approval links
    API_BASE_URL = os.environ.get('API_BASE_URL', '')
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Cache timeouts (in seconds)
    CACHE_TIMEOUT = 300  # 5 minutes default
    EVENT_CACHE_TIMEOUT = 600  # 10 minutes
    USER_CACHE_TIMEOUT = 1800  # 30 minutes
    OTP_TIMEOUT = 300  # 10 minutes