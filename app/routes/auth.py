from flask import Blueprint, request, jsonify
import bcrypt
import jwt
from datetime import datetime, timedelta
from config import Config
from app.models.user import User
import re

auth_bp = Blueprint('auth', __name__)

def init_auth_routes(mongo):
    user_model = User(mongo)

    @auth_bp.route('/register', methods=['POST'])
    def register():
        data = request.get_json()
        
        # Check required fields
        required_fields = ['enrollment_number', 'password', 'name', 'email', 'branch', 'year']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        # Validate enrollment number format (assuming format like "20BAI1234")
        if not re.match(r'^\d{2}[A-Z]{3}\d{4}$', data['enrollment_number']):
            return jsonify({'message': 'Invalid enrollment number format'}), 400

        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data['email']):
            return jsonify({'message': 'Invalid email format'}), 400

        # Validate year (1-4)
        try:
            year = int(data['year'])
            if year not in range(1, 5):
                return jsonify({'message': 'Year must be between 1 and 4'}), 400
        except ValueError:
            return jsonify({'message': 'Invalid year format'}), 400

        if user_model.user_exists(data['enrollment_number']):
            return jsonify({'message': 'User already exists'}), 400

        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        user_id = user_model.create_user(data, hashed_password)

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