import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/event_management')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24 hours 
    
    # Add file upload configs
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'static/uploads'
    
    # Add MongoDB client options
    MONGO_OPTIONS = {
        'serverSelectionTimeoutMS': 5000,  # 5 second timeout
        'connectTimeoutMS': 10000,  # 10 second timeout
        'socketTimeoutMS': 10000  # 10 second timeout
    }