import random
from datetime import datetime, timedelta, timezone
import json
from config import Config
from .mail import MailgunMailer
from ..extensions import redis_client

class OTPManager:
    def __init__(self, mongo):
        self.mailer = MailgunMailer()
        
    def generate_otp(self):
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    def save_otp(self, email, otp):
        redis_client.setex(
            f"otp:{email}", 
            Config.OTP_TIMEOUT,
            json.dumps({
                'otp': otp,
                'verified': False,
                'created_at': datetime.now(timezone.utc).isoformat()
            })
        )

    def verify_otp(self, email, otp):
        otp_data = redis_client.get(f"otp:{email}")
        if not otp_data:
            return False
            
        data = json.loads(otp_data)
        if data['otp'] == otp and not data['verified']:
            # Mark as verified
            data['verified'] = True
            redis_client.setex(
                f"otp:{email}",
                Config.OTP_TIMEOUT,
                json.dumps(data)
            )
            return True
        return False

    def send_otp_email(self, email, otp):
        return self.mailer.send_otp_email(email, otp)
    
    def send_password_reset_email(self, email, otp):
        return self.mailer.send_password_reset_email(email, otp)
