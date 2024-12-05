from datetime import datetime
from flask_pymongo import PyMongo
from bson import ObjectId

class User:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users

    def create_user(self, user_data, password_hash):
        user = {
            'enrollment_number': user_data['enrollment_number'],
            'password': password_hash,
            'name': user_data['name'],
            'email': user_data['email'],
            'branch': user_data['branch'],
            'year': int(user_data['year']),
            'created_at': datetime.now(datetime.UTC)
        }
        result = self.collection.insert_one(user)
        return result.inserted_id

    def get_user_by_enrollment(self, enrollment_number):
        return self.collection.find_one({'enrollment_number': enrollment_number})

    def user_exists(self, enrollment_number):
        return self.collection.count_documents({'enrollment_number': enrollment_number}) > 0

    def get_user_details(self, enrollment_number):
        user = self.collection.find_one(
            {'enrollment_number': enrollment_number},
            {'password': 0}  # Exclude password from results
        )
        if user:
            user['_id'] = str(user['_id'])
        return user