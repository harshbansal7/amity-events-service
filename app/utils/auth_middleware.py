from functools import wraps
from flask import request, jsonify
import jwt
from config import Config

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            current_user = data['enrollment_number']
            
            # If user is external, check if their event still exists
            if data.get('is_external'):
                kwargs['event_id'] = str(data['event_id'])
                kwargs['is_external'] = True

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            print(f"Token validation error: {str(e)}")
            return jsonify({'message': 'Token is invalid'}), 401

        return f(current_user, *args, **kwargs)
    
    return decorated 