import requests
from config import Config

class MailgunMailer:
    def __init__(self):
        self.api_key = Config.MAILGUN_API_KEY
        self.domain = Config.MAILGUN_DOMAIN
        self.from_email = Config.MAILGUN_FROM_EMAIL
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"

    def send_email(self, to_email, subject, text=None, html=None):
        """
        Send an email using Mailgun API
        """
        try:
            data = {
                "from": f"Amity Events <{self.from_email}>",
                "to": [to_email],
                "subject": subject
            }

            if text:
                data["text"] = text
            if html:
                data["html"] = html

            response = requests.post(
                f"{self.base_url}/messages",
                auth=("api", self.api_key),
                data=data
            )

            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            print(f"Failed to send email: {str(e)}")
            return False

    def send_otp_email(self, to_email, otp):
        """
        Send OTP verification email
        """
        subject = "Your OTP for Amity Events Registration"
        
        text = f"""
        Hello,

        Your OTP for Amity Events registration is: {otp}

        This OTP will expire in 10 minutes.

        Best regards,
        Amity Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">Amity Events Registration</h2>
            <p>Hello,</p>
            <p>Your OTP for registration is:</p>
            <div style="background-color: #F3F4F6; padding: 20px; text-align: center; border-radius: 8px;">
                <h1 style="color: #4F46E5; font-size: 32px; margin: 0;">{otp}</h1>
            </div>
            <p style="color: #6B7280; font-size: 14px;">This OTP will expire in 10 minutes.</p>
            <p>Best regards,<br>Amity Events Team</p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html) 