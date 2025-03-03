from flask import Blueprint, request, jsonify
from app.models.user import User
from app.models.event import Event
from app.models.external_participant import ExternalParticipant
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
    external_participant_model = ExternalParticipant(mongo)
    event_model = Event(mongo)

    def is_valid_amity_email(email):
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@(s|ch|pb)\.amity\.edu$', email))

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

        # Check if it's an external participant (enrollment starts with 'EXT')
        if data['enrollment_number'].startswith('EXT'):
            user = external_participant_model.get_by_temp_enrollment(data['enrollment_number'])
            if not user:
                return jsonify({'error': 'Invalid credentials'}), 401
                
            if not check_password_hash(data['password'], user['password']):
                return jsonify({'error': 'Invalid credentials'}), 401

            # Generate JWT token for external participant
            token = jwt.encode({
                'enrollment_number': user['temp_enrollment'],
                'name': user['name'],
                'exp': datetime.now(timezone.utc) + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES),
                'is_external': True,
                'event_code': user['event_code']
            }, Config.JWT_SECRET_KEY)

            return jsonify({
                'token': token,
                'user': {
                    'name': user['name'],
                    'enrollment_number': user['temp_enrollment'],
                    'email': user['email'],
                    'is_external': True
                }
            }), 200

        user = user_model.get_user_by_enrollment(data['enrollment_number'], True)
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
            
        if not check_password_hash(data['password'], user['password']):
            return jsonify({'error': 'Invalid credentials'}), 401

        if not user.get('email_verified', False):
            return jsonify({'error': 'Email not verified'}), 401

        # Generate JWT token
        token = jwt.encode({
            'enrollment_number': user['enrollment_number'],
            'name': user['name'],
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

    @auth.route('/verify-event-code', methods=['POST'])
    def verify_event_code():
        data = request.get_json()
        event_code = data.get('event_code')
        
        if not event_code:
            return jsonify({'error': 'Event code is required'}), 400

        event = mongo.db.events.find_one({
            'event_code': event_code,
            'allow_external': True,
            'date': {
                '$gte': datetime.now(timezone.utc)
            }
        })
        
        if not event:
            return jsonify({'error': 'Invalid or expired event code'}), 400

        return jsonify({
            'message': 'Valid event code',
            'event_name': event['name']
        }), 200

    @auth.route('/register-external', methods=['POST'])
    def register_external():
        data = request.get_json()
        
        # Validate event code
        event = mongo.db.events.find_one({
            'event_code': data.get('event_code'),
            'allow_external': True
        })
        
        if not event:
            return jsonify({'error': 'Invalid event code'}), 400

        # Generate temporary credentials
        temp_enrollment, temp_password = external_participant_model.generate_temp_credentials()
        
        # Create external participant
        password_hash = generate_password_hash(temp_password)
        participant_data = {
            'name': data['name'],
            'email': data['email'],
            'phone_number': data['phone_number'],
            'temp_enrollment': temp_enrollment
        }
        
        participant_id = external_participant_model.create_external_participant(
            participant_data, 
            event['event_code'],
            password_hash
        )

        # Send credentials via email
        credentials = {
            'enrollment_number': temp_enrollment,
            'password': temp_password
        }
        
        from app.utils.mail import MailgunMailer
        mailer = MailgunMailer()
        mailer.send_external_credentials(
            data['email'],
            data['name'],
            event['name'],
            credentials
        )

        return jsonify({
            'message': 'Registration successful',
            'credentials': {
                'enrollment_number': temp_enrollment,
                'password': temp_password
            }
        }), 201

    @auth.route('/forgot-password', methods=['POST'])
    def forgot_password():
        data = request.get_json()
        email = data.get('email')

        if not email or not is_valid_amity_email(email):
            return jsonify({'error': 'Please provide a valid Amity email address'}), 400

        # Check if user exists
        user = user_model.get_user_by_email(email)
        if not user:
            return jsonify({'error': 'No account found with this email'}), 404

        # Generate and save reset token
        # reset_token = user_model.create_password_reset_token(email)
        
        # Send reset email
        otp = otp_manager.generate_otp()
        otp_manager.save_otp(email, otp)
        
        if otp_manager.send_password_reset_email(email, otp):
            return jsonify({'message': 'Password reset instructions sent'}), 200
        return jsonify({'error': 'Failed to send reset instructions'}), 500

    @auth.route('/verify-reset-otp', methods=['POST'])
    def verify_reset_otp():
        data = request.get_json()
        email = data.get('email')
        otp = data.get('otp')

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required'}), 400

        if otp_manager.verify_otp(email, otp):
            reset_token = user_model.create_password_reset_token(email)
            return jsonify({
                'message': 'OTP verified successfully',
                'reset_token': reset_token
            }), 200
        return jsonify({'error': 'Invalid or expired OTP'}), 400

    @auth.route('/reset-password', methods=['POST'])
    def reset_password():
        data = request.get_json()
        reset_token = data.get('reset_token')
        new_password = data.get('new_password')

        if not reset_token or not new_password:
            return jsonify({'error': 'Reset token and new password are required'}), 400

        try:
            # Verify reset token and update password
            email = user_model.verify_reset_token(reset_token)
            if not email:
                return jsonify({'error': 'Invalid or expired reset token'}), 400

            # Update password
            password_hash = generate_password_hash(new_password)
            user_model.update_password(email, password_hash)

            return jsonify({'message': 'Password updated successfully'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    return auth 