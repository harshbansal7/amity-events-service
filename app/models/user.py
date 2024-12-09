from datetime import datetime, timezone
from flask_pymongo import PyMongo
from bson import ObjectId

class User:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users

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
        return result.inserted_id

    def get_user_by_email(self, amity_email):
        return self.collection.find_one({'amity_email': amity_email})

    def get_user_by_enrollment(self, enrollment_number):
        return self.collection.find_one({'enrollment_number': enrollment_number})

    def update_email_verification(self, amity_email, verified=True):
        print("Verifying email", amity_email, verified)
        return self.collection.update_one(
            {'amity_email': amity_email},
            {'$set': {'email_verified': verified}}
        )

    def user_exists(self, amity_email=None, enrollment_number=None):
        query = {}
        if amity_email:
            query['amity_email'] = amity_email
        if enrollment_number:
            query['enrollment_number'] = enrollment_number
        return self.collection.count_documents(query) > 0

    def get_user_details(self, enrollment_number):
        user = self.collection.find_one(
            {'enrollment_number': enrollment_number},
            {'password': 0}  # Exclude password from results
        )
        if user:
            user['_id'] = str(user['_id'])
        return user