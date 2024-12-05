from flask import Flask, jsonify, send_from_directory
from flask_pymongo import PyMongo
from pymongo.errors import ServerSelectionTimeoutError
from config import Config
from app.routes.auth import init_auth_routes
from app.routes.events import init_event_routes
from flask_cors import CORS
import os

mongo = PyMongo()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Add static file configuration
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Test MongoDB connection
    try:
        mongo.init_app(app)
        # Verify connection
        mongo.db.command('ping')
        print("Successfully connected to MongoDB!")
    except ServerSelectionTimeoutError:
        print("Could not connect to MongoDB. Please check your connection string and network connection.")
        
    # Register blueprints
    app.register_blueprint(init_auth_routes(mongo), url_prefix='/api/auth')
    app.register_blueprint(init_event_routes(mongo), url_prefix='/api')

    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:3000",
                "https://amityevents.vercel.app"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"]
        },
        r"/static/*": {
            "origins": "*"
        }
    })

    @app.errorhandler(ServerSelectionTimeoutError)
    def handle_mongo_error(error):
        return jsonify({"error": "Database connection error. Please try again later."}), 500

    # Add route to serve uploaded files
    @app.route('/static/uploads/<filename>')
    def serve_image(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    return app 