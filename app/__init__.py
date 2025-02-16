from flask import Flask, request, g
from flask_cors import CORS
from flask_pymongo import PyMongo
from config import Config
from app.utils.datadog_logger import DatadogLogger

mongo = PyMongo()
dd_logger = DatadogLogger()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    CORS(app, supports_credentials=True)
    mongo.init_app(app)

    # Register Datadog middleware
    @app.before_request
    def before_request():
        if app.config['ENABLE_DATADOG']:
            dd_logger.log_request()

    @app.after_request
    def after_request(response):
        if app.config['ENABLE_DATADOG']:
            return dd_logger.log_response(response)
        return response

    @app.errorhandler(Exception)
    def handle_error(error):
        if app.config['ENABLE_DATADOG']:
            dd_logger.log_error(error)
        raise error

    # Register blueprints
    from app.routes.auth import init_auth_routes
    from app.routes.events import init_event_routes
    
    app.register_blueprint(init_auth_routes(mongo), url_prefix='/api/auth')
    app.register_blueprint(init_event_routes(mongo), url_prefix='/api/events')

    return app 