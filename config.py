import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/event_management")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24 hours
    FIVEMERR_API_KEY = os.getenv("FIVEMERR_API_KEY", "")

    # Mailgun Configuration
    MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
    MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL", "noreply@aup.events")

    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # Event approval configuration
    EVENT_APPROVAL_REQUIRED = os.getenv("EVENT_APPROVAL_REQUIRED", "True").lower() in (
        "true",
        "1",
        "t",
    )

    # API base URL for direct approval links
    API_BASE_URL = os.environ.get("API_BASE_URL", "")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "support@aup.events")
    ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "admin")
