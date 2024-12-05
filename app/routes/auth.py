from flask import Blueprint, request, jsonify
import bcrypt
import jwt
from datetime import datetime, timedelta
from config import Config
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

def init_auth_routes(mongo):
    user_model = User(mongo)

    @auth_bp.route('/register', methods=['POST'])
    def register():
        data = request.get_json()
        
        if not data or not data.get('enrollment_number') or not data.get('password'):
            return jsonify({'message': 'Missing required fields'}), 400

        if user_model.user_exists(data['enrollment_number']):
            return jsonify({'message': 'User already exists'}), 400

        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        user_id = user_model.create_user(data['enrollment_number'], hashed_password)

        return jsonify({'message': 'User created successfully'}), 201

    @auth_bp.route('/login', methods=['POST'])
    def login():
        data = request.get_json()

        if not data or not data.get('enrollment_number') or not data.get('password'):
            return jsonify({'message': 'Missing required fields'}), 400

        user = user_model.get_user_by_enrollment(data['enrollment_number'])
        
        if not user or not bcrypt.checkpw(data['password'].encode('utf-8'), user['password']):
            return jsonify({'message': 'Invalid credentials'}), 401

        token = jwt.encode({
            'enrollment_number': user['enrollment_number'],
            'exp': datetime.utcnow() + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
        }, Config.JWT_SECRET_KEY)

        return jsonify({'token': token}), 200

    return auth_bp 