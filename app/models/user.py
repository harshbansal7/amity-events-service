from datetime import datetime, timezone, timedelta
import jwt
from flask_pymongo import PyMongo
from bson import ObjectId, json_util
import json
from config import Config
from ..extensions import redis_client
from ..utils.json_encoder import custom_dumps, custom_loads

class User:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users

    def _cache_key_user(self, identifier):
        return f"user:{identifier}"

    def create_user(self, user_data, password_hash):
        user = {
            'name': user_data['name'],
            'amity_email': user_data['amity_email'],
            'enrollment_number': user_data['enrollment_number'],
            'password': password_hash,
            'branch': user_data['branch'],
            'year': int(user_data['year']),
            'phone_number': user_data['phone_number'],
            'email_verified': True,
            'created_at': datetime.now(timezone.utc)
        }
        result = self.collection.insert_one(user)
        
        # Cache the new user (excluding password)
        user_cache = user.copy()
        del user_cache['password']
        redis_client.setex(
            self._cache_key_user(user['enrollment_number']), 
            Config.USER_CACHE_TIMEOUT,
            custom_dumps(user_cache)
        )
        redis_client.setex(
            self._cache_key_user(user['amity_email']),
            Config.USER_CACHE_TIMEOUT,
            custom_dumps(user_cache)
        )
        
        return result.inserted_id

    def get_user_by_email(self, amity_email):
        # Try cache first
        cache_key = self._cache_key_user(amity_email)
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            return custom_loads(cached_data)
            
        user = self.collection.find_one({'amity_email': amity_email})
        if user:
            # Cache user data (excluding password)
            user_cache = {k:v for k,v in user.items() if k != 'password'}
            redis_client.setex(
                cache_key,
                Config.USER_CACHE_TIMEOUT,
                custom_dumps(user_cache)
            )
            
        return user

    def get_user_by_enrollment(self, enrollment_number, for_login=False):    
        # Try cache first
        cache_key = self._cache_key_user(enrollment_number)
        cached_data = redis_client.get(cache_key)
        
        if cached_data and not for_login:
            return custom_loads(cached_data)
            
        user = self.collection.find_one({'enrollment_number': enrollment_number})
        if user:
            # Cache user data (excluding password)
            user_cache = {k:v for k,v in user.items() if k != 'password'}
            # Convert ObjectId to string before caching
            if '_id' in user_cache:
                user_cache['_id'] = str(user_cache['_id'])
            redis_client.setex(
                cache_key,
                Config.USER_CACHE_TIMEOUT,
                custom_dumps(user_cache)
            )
            
        return user

    def update_email_verification(self, amity_email, verified=True):
        result = self.collection.update_one(
            {'amity_email': amity_email},
            {'$set': {'email_verified': verified}}
        )
        
        # Invalidate cache
        redis_client.delete(self._cache_key_user(amity_email))
        user = self.get_user_by_email(amity_email)
        if user:
            redis_client.delete(self._cache_key_user(user['enrollment_number']))
            
        return result

    def user_exists(self, amity_email=None, enrollment_number=None):
        # Try cache first
        if amity_email:
            if redis_client.exists(self._cache_key_user(amity_email)):
                return True
        if enrollment_number:
            if redis_client.exists(self._cache_key_user(enrollment_number)):
                return True
                
        # If not in cache, check database
        query = {}
        if amity_email:
            query['amity_email'] = amity_email
        if enrollment_number:
            query['enrollment_number'] = enrollment_number
        return self.collection.count_documents(query) > 0

    def get_user_details(self, enrollment_number):
        # Try cache first
        cache_key = self._cache_key_user(enrollment_number)
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            data = custom_loads(cached_data)
            if '_id' in data:
                data['_id'] = str(data['_id'])
            return data
            
        user = self.collection.find_one(
            {'enrollment_number': enrollment_number},
            {'password': 0}  # Exclude password
        )
        if user:
            user['_id'] = str(user['_id'])
            # Cache the result
            redis_client.setex(
                cache_key,
                Config.USER_CACHE_TIMEOUT,
                custom_dumps(user)
            )
        return user

    def create_password_reset_token(self, email):
        token = jwt.encode({
            'email': email,
            'exp': datetime.now(timezone.utc) + timedelta(minutes=30)
        }, Config.JWT_SECRET_KEY)
        return token

    def verify_reset_token(self, token):
        try:
            data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            return data['email']
        except:
            return None

    def update_password(self, email, password_hash):
        result = self.collection.update_one(
            {'amity_email': email},
            {'$set': {'password': password_hash}}
        )
        
        # Invalidate cache
        redis_client.delete(self._cache_key_user(email))
        user = self.get_user_by_email(email)
        if user:
            redis_client.delete(self._cache_key_user(user['enrollment_number']))
            
        return result.modified_count > 0