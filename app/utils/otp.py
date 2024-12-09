import random
from datetime import datetime, timedelta, timezone

from config import Config
from .mail import MailgunMailer

class OTPManager:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.otps
        self.mailer = MailgunMailer()

    def generate_otp(self):
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    def save_otp(self, email, otp):
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        self.collection.insert_one({
            'email': email,
            'otp': otp,
            'expiry': expiry,
            'verified': False
        })

    def verify_otp(self, email, otp):
        otp_record = self.collection.find_one({
            'email': email,
            'otp': otp,
            'expiry': {'$gt': datetime.now(timezone.utc)},
            'verified': False
        })
        
        if otp_record:
            self.collection.update_one(
                {'_id': otp_record['_id']},
                {'$set': {'verified': True}}
            )
            return True
        return False

    def send_otp_email(self, email, otp):
        return self.mailer.send_otp_email(email, otp) 