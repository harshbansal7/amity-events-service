from datetime import datetime
from flask_pymongo import PyMongo
from bson import ObjectId

class User:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users

    def create_user(self, enrollment_number, password_hash):
        user = {
            'enrollment_number': enrollment_number,
            'password': password_hash,
            'created_at': datetime.utcnow()
        }
        result = self.collection.insert_one(user)
        return result.inserted_id

    def get_user_by_enrollment(self, enrollment_number):
        return self.collection.find_one({'enrollment_number': enrollment_number})

    def user_exists(self, enrollment_number):
        return self.collection.count_documents({'enrollment_number': enrollment_number}) > 0 