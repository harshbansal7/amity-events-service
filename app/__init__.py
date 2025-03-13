from flask import Flask, jsonify
from flask_pymongo import PyMongo
from pymongo.errors import ServerSelectionTimeoutError
from config import Config
from app.routes.auth import init_auth_routes
from app.routes.events import init_event_routes
from flask_cors import CORS

mongo = PyMongo()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Test MongoDB connection
    try:
        mongo.init_app(app)
        # Verify connection
        mongo.db.command("ping")
        print("Successfully connected to MongoDB!")
    except ServerSelectionTimeoutError:
        print(
            "Could not connect to MongoDB. Please check your connection string and network connection."
        )

    # Register blueprints
    app.register_blueprint(init_auth_routes(mongo), url_prefix="/api/auth")
    app.register_blueprint(init_event_routes(mongo), url_prefix="/api")

    # Configure CORS
    allowed_origins = [
        "https://www.aup.events",
        "https://aup.events",
        "https://app.aup.events",
    ]
    if app.config["FLASK_ENV"] == "development":
        allowed_origins.append("http://localhost:3000")

    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        expose_headers=["Content-Type", "Authorization"],
    )

    @app.errorhandler(ServerSelectionTimeoutError)
    def handle_mongo_error(error):
        return (
            jsonify({"error": "Database connection error. Please try again later."}),
            500,
        )

    return app
