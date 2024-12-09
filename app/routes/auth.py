from flask import Blueprint, request, jsonify
from app.models.user import User
from app.utils.otp import OTPManager
from app.utils.password import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta, timezone
from config import Config
import re

def init_auth_routes(mongo):
    auth = Blueprint('auth', __name__)
    user_model = User(mongo)
    otp_manager = OTPManager(mongo)

    def is_valid_amity_email(email):
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@s\.amity\.edu$', email))

    @auth.route('/verify-email', methods=['POST'])
    def verify_email():
        data = request.get_json()
        email = data.get('email')

        if not email or not is_valid_amity_email(email):
            return jsonify({'error': 'Please provide a valid Amity email address'}), 400

        # Check if email is already registered
        if user_model.user_exists(amity_email=email):
            return jsonify({'error': 'Email already registered'}), 400

        otp = otp_manager.generate_otp()
        otp_manager.save_otp(email, otp)
        
        if otp_manager.send_otp_email(email, otp):
            return jsonify({'message': 'OTP sent successfully'}), 200
        return jsonify({'error': 'Failed to send OTP'}), 500

    @auth.route('/verify-otp', methods=['POST'])
    def verify_otp():
        data = request.get_json()
        email = data.get('email')
        otp = data.get('otp')

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required'}), 400

        if otp_manager.verify_otp(email, otp):
            return jsonify({'message': 'OTP verified successfully'}), 200
        return jsonify({'error': 'Invalid or expired OTP'}), 400

    @auth.route('/register', methods=['POST'])
    def register():
        data = request.get_json()
        
        required_fields = ['name', 'amity_email', 'enrollment_number', 'password', 
                         'branch', 'year', 'phone_number']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'All fields are required'}), 400

        # Validate email format
        if not is_valid_amity_email(data['amity_email']):
            return jsonify({'error': 'Invalid Amity email address'}), 400

        # Check if user already exists
        if user_model.user_exists(amity_email=data['amity_email']):
            return jsonify({'error': 'Email already registered'}), 400

        if user_model.user_exists(enrollment_number=data['enrollment_number']):
            return jsonify({'error': 'Enrollment number already registered'}), 400

        # Create user
        password_hash = generate_password_hash(data['password'])
        user_id = user_model.create_user(data, password_hash)

        return jsonify({
            'message': 'Registration successful',
            'user_id': str(user_id)
        }), 201

    @auth.route('/login', methods=['POST'])
    def login():
        data = request.get_json()
        
        if not data or not data.get('enrollment_number') or not data.get('password'):
            return jsonify({'error': 'Enrollment number and password are required'}), 400

        user = user_model.get_user_by_enrollment(data['enrollment_number'])
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
            
        if not check_password_hash(data['password'], user['password']):
            return jsonify({'error': 'Invalid credentials'}), 401

        if not user.get('email_verified', False):
            return jsonify({'error': 'Email not verified'}), 401

        # Generate JWT token
        token = jwt.encode({
            'enrollment_number': user['enrollment_number'],
            'exp': datetime.now(timezone.utc) + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
        }, Config.JWT_SECRET_KEY)

        return jsonify({
            'token': token,
            'user': {
                'name': user['name'],
                'enrollment_number': user['enrollment_number'],
                'amity_email': user['amity_email'],
                'branch': user['branch'],
                'year': user['year']
            }
        }), 200

    return auth 