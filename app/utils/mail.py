import requests
from config import Config
from datetime import datetime

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
                "from": f"AUP Events <{self.from_email}>",
                "to": [to_email],
                "h:Reply-To": "support@aup.events",
                "h:X-Mailgun-Variables": '{"category": "user-notification"}',
                "h:List-Unsubscribe": f"<mailto:unsubscribe@{self.domain}>",
                "subject": subject
            }

            if text:
                data["text"] = text
            if html:
                data["html"] = html

            headers = {
                "h:X-Mailgun-Track": "yes",
                "h:X-Mailgun-Track-Clicks": "yes",
                "h:X-Mailgun-Track-Opens": "yes",
                "h:X-Mailgun-Dkim": "yes",
                "h:X-Mailgun-SPF": "yes"
            }
            data.update(headers)

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
        subject = "Your Verification Code for AUP Events"
        
        text = f"""
        Hi there!

        Thank you for registering with AUP Events - Your Campus Event Hub.
        
        Your verification code is: {otp}

        This code will expire in 10 minutes for security purposes.

        If you didn't request this code, please ignore this email.

        Best wishes,
        The AUP Events Team

        Need help? Contact us at support@aup.events
        
        © {datetime.now().year} AUP Events. All rights reserved.
        Amity University, Sector 125, Noida, Uttar Pradesh 201313
        """

        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #ffffff;">
            <img src="https://www.aup.events/assets/amity-logo.png" alt="AUP Events Logo" style="width: 120px; margin-bottom: 20px;">
            <h2 style="color: #4F46E5; font-size: 24px; margin-bottom: 20px;">Welcome to AUP Events!</h2>
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hi there!</p>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">Thank you for registering with AUP Events - Your Campus Event Hub.</p>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">Your verification code is:</p>
            
            <div style="background-color: #F3F4F6; padding: 20px; text-align: center; border-radius: 12px; margin: 20px 0;">
                <h1 style="color: #4F46E5; font-size: 36px; margin: 0; letter-spacing: 4px; font-family: monospace;">{otp}</h1>
            </div>
            
            <p style="color: #6B7280; font-size: 14px;">This code will expire in 10 minutes for security purposes.</p>
            
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #E5E7EB;">
                <p style="color: #374151; font-size: 14px; margin-bottom: 10px;">Best wishes,<br>The AUP Events Team</p>
                
                <p style="color: #6B7280; font-size: 14px; margin-bottom: 5px;">Need help? Contact us at <a href="mailto:support@aup.events" style="color: #4F46E5; text-decoration: none;">support@aup.events</a></p>
                
                <p style="color: #9CA3AF; font-size: 12px; margin-top: 20px;">
                    © {datetime.now().year} AUP Events. All rights reserved.<br>
                    Amity University, Sector 125, Noida, Uttar Pradesh 201313
                </p>
            </div>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html)

    def send_external_credentials(self, to_email, name, event_name, credentials):
        """
        Send credentials to external participant
        """
        subject = f"Your Login Credentials for {event_name}"
        
        text = f"""
        Hello {name},

        Thank you for registering for {event_name}. Here are your login credentials:

        Enrollment Number: {credentials['enrollment_number']}
        Password: {credentials['password']}

        Please save these credentials as they cannot be recovered later.
        You can use these credentials to login and view event details.

        Best regards,
        Amity Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">Amity Events Registration</h2>
            <p>Hello {name},</p>
            <p>Thank you for registering for <strong>{event_name}</strong>. Here are your login credentials:</p>
            <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; font-family: monospace; font-size: 16px;">
                    <strong>Enrollment Number:</strong> {credentials['enrollment_number']}<br>
                    <strong>Password:</strong> {credentials['password']}
                </p>
            </div>
            <p style="color: #DC2626; font-weight: bold;">
                Please save these credentials as they cannot be recovered later.
            </p>
            <p>You can use these credentials to login and view event details.</p>
            <p>Best regards,<br>Amity Events Team</p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html)

    def send_password_reset_email(self, to_email, otp):
        """Send password reset email with OTP"""
        subject = "Reset Your Amity Events Password"
        
        text = f"""
        Hello,

        You have requested to reset your password for Amity Events.
        Your password reset OTP is: {otp}

        This OTP will expire in 10 minutes.
        If you did not request this reset, please ignore this email.

        Best regards,
        Amity Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">Reset Your Password</h2>
            <p>Hello,</p>
            <p>You have requested to reset your password for Amity Events.</p>
            <p>Your password reset OTP is:</p>
            <div style="background-color: #F3F4F6; padding: 20px; text-align: center; border-radius: 8px;">
                <h1 style="color: #4F46E5; font-size: 32px; margin: 0;">{otp}</h1>
            </div>
            <p style="color: #6B7280; font-size: 14px;">This OTP will expire in 10 minutes.</p>
            <p style="color: #DC2626; font-size: 14px;">
                If you did not request this reset, please ignore this email.
            </p>
            <p>Best regards,<br>Amity Events Team</p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html) 