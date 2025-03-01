import requests
from config import Config
from datetime import datetime, timezone

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
                "subject": subject,
                "text": text,
                "date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z"),
                "h:List-Unsubscribe": f"<mailto:unsubscribe@{self.domain}?subject=unsubscribe>",
                "h:Reply-To": "support@aup.events",
                "h:X-Mailgun-Tag": "registration",
                "h:X-Priority": "3",
                "h:X-MSMail-Priority": "Normal",
                "o:tag": ["registration", "user-notification"],
                "o:tracking": False,
                "o:tracking-opens": False,
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
        
        © {datetime.now().year} Harsh Bansal. All rights reserved.
        """

        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #ffffff;">
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
                    © {datetime.now().year} Harsh Bansal. All rights reserved.
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
        AUP Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">AUP Events Registration</h2>
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
            <p>Best regards,<br>AUP Events Team</p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html)

    def send_password_reset_email(self, to_email, otp):
        """Send password reset email with OTP"""
        subject = "Reset Your AUP Events Password"
        
        text = f"""
        Hello,

        You have requested to reset your password for AUP Events.
        Your password reset OTP is: {otp}

        This OTP will expire in 10 minutes.
        If you did not request this reset, please ignore this email.

        Best regards,
        AUP Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">Reset Your Password</h2>
            <p>Hello,</p>
            <p>You have requested to reset your password for AUP Events.</p>
            <p>Your password reset OTP is:</p>
            <div style="background-color: #F3F4F6; padding: 20px; text-align: center; border-radius: 8px;">
                <h1 style="color: #4F46E5; font-size: 32px; margin: 0;">{otp}</h1>
            </div>
            <p style="color: #6B7280; font-size: 14px;">This OTP will expire in 10 minutes.</p>
            <p style="color: #DC2626; font-size: 14px;">
                If you did not request this reset, please ignore this email.
            </p>
            <p>Best regards,<br>AUP Events Team</p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html) 
    
    def send_event_registration_confirmation(self, to_email, name, event_name, event_date, venue, organizer_email):
        """Send a professional event registration confirmation email to the participant."""
        subject = f"🎉 Registration Confirmed: {event_name}"

        text = f"""
        Dear {name},

        We are pleased to confirm your registration for "{event_name}" on AUP Events. 
        Your participation is now successfully recorded.

        📅 Event: {event_name}
        📆 Date: {event_date}
        🏢 Venue: {venue}
        

        Stay tuned for further details, and feel free to reach out if you have any questions.
        
        Organiser: {organizer_email}

        Looking forward to your participation!

        Best regards,  
        AUP Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #4F46E5; text-align: center;">🎉 Registration Confirmed</h2>
            <p>Dear {name},</p>
            <p>We are delighted to confirm your registration for <strong>{event_name}</strong> on AUP Events.</p>
            
            <div style="background-color: #f4f4f4; padding: 10px; border-radius: 8px;">
                <p><strong>📅 Event:</strong> {event_name}</p>
                <p><strong>📆 Date:</strong> {event_date}</p>
                <p><strong>🏢 Venue:</strong> {venue}</p>
            </div>

            <p>Stay tuned for more details, and if you have any questions, feel free to contact the organiser at <a href="mailto:{organizer_email}" style="color: #4F46E5;">{organizer_email}</a>.</p>
            <p>Looking forward to your participation!</p>

            <p style="margin-top: 20px;">Best regards,</p>
            <p><strong>AUP Events Team</strong></p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html)

    def send_event_registration_notification(self, to_email, name, event_name):
        """Send a notification email to the event organizer about a new registration"""
        
        subject = f"🎉 New Registration: {name} for {event_name}!"
        
        text = f"""
        Hi there,

        Great news! {name} has successfully registered for {event_name} on AUP Events.

        Stay tuned for further updates and ensure a seamless experience for all attendees.

        Best regards,  
        The AUP Events Team
        """

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #4F46E5;">🎉 New Registration Alert!</h2>
            <p>Hello,</p>
            <p><strong>{name}</strong> has just registered for <strong>{event_name}</strong> on AUP Events.</p>
            <p>Make sure to check the attendee list and stay prepared for a great event!</p>
            <p>Best regards,<br><strong>The AUP Events Team</strong></p>
        </div>
        """

        return self.send_email(to_email, subject, text=text, html=html)
        
    def send_event_approval_request(self, to_email, event_data, creator_data, approval_url, token):
        """Send event approval request to admin with approval link and token"""
        event_name = event_data.get('name', 'Unnamed Event')
        event_date = event_data.get('date', '')
        venue = event_data.get('venue', '')
        creator_name = creator_data.get('name', 'Unknown')
        creator_email = creator_data.get('amity_email', 'Unknown')
        description = event_data.get('description', 'No description provided')
        event_id = str(event_data.get('_id', ''))
        
        # Format date if it's a string
        if isinstance(event_date, str):
            try:
                event_date = datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S.%f")
                event_date = event_date.strftime("%B %d, %Y at %I:%M %p")
            except ValueError:
                try:
                    event_date = datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S")
                    event_date = event_date.strftime("%B %d, %Y at %I:%M %p")
                except ValueError:
                    pass  # Keep as is if parsing fails
        
        # Create a direct API approval URL that doesn't require the frontend
        api_base_url = getattr(Config, 'API_BASE_URL', '')
        if not api_base_url:
            # Extract domain from frontend URL if API URL not configured
            frontend_url = getattr(Config, 'FRONTEND_URL', '')
            if frontend_url and frontend_url.startswith('https://'):
                domain = frontend_url.split('//', 1)[1].split('/', 1)[0]
                api_base_url = f"https://api.{domain}"
            else:
                api_base_url = "https://api.aup.events"
        
        # Direct approval link that will work with the GET endpoint we created
        direct_approval_url = f"{api_base_url}/api/admin/events/{event_id}/approve?token={token}"
        
        subject = f"🔔 New Event Approval Request: {event_name}"
        
        text = f"""
        Hello Admin,
        
        A new event requires your approval:
        
        Event Name: {event_name}
        Date: {event_date}
        Venue: {venue}
        Creator: {creator_name} ({creator_email})
        
        Description:
        {description}
        
        To approve this event, please click here: {direct_approval_url}
        
        Your approval token is: {token}
        
        Thank you,
        AUP Events System
        """
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
            <h2 style="color: #4F46E5; text-align: center;">New Event Approval Request</h2>
            
            <p>Hello Admin,</p>
            
            <p>A new event requires your approval:</p>
            
            <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Event Name:</strong> {event_name}</p>
                <p><strong>Date:</strong> {event_date}</p>
                <p><strong>Venue:</strong> {venue}</p>
                <p><strong>Creator:</strong> {creator_name} ({creator_email})</p>
                <p><strong>Description:</strong></p>
                <p style="padding: 10px; background-color: white; border-radius: 3px;">{description}</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{direct_approval_url}" style="background-color: #4F46E5; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Approve Event</a>
            </div>
            
            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
            <p style="background-color: #f4f4f4; padding: 10px; border-radius: 3px; word-break: break-all;">{direct_approval_url}</p>
            
            <p>Your approval token is: <strong>{token}</strong></p>
            
            <p style="margin-top: 20px; font-size: 14px; color: #666;">Thank you,<br>AUP Events System</p>
        </div>
        """
        
        return self.send_email(to_email, subject, text=text, html=html)
        
    def send_event_pending_notification(self, to_email, event_name, event_date):
        """Send notification to event creator that their event is pending approval"""
        
        subject = f"⏳ Event Pending Approval: {event_name}"
        
        text = f"""
        Hello,
        
        Thank you for creating the event "{event_name}" scheduled for {event_date}.
        
        Your event has been submitted and is currently awaiting admin approval. You will receive another email once your event has been reviewed.
        
        While waiting for approval, you can make any necessary preparations for your event.
        
        Thank you for using AUP Events!
        
        Best regards,
        AUP Events System
        """
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
            <h2 style="color: #4F46E5; text-align: center;">Event Pending Approval</h2>
            
            <div style="text-align: center; margin: 20px 0;">
                <span style="font-size: 48px;">⏳</span>
            </div>
            
            <p>Hello,</p>
            
            <p>Thank you for creating the event <strong>"{event_name}"</strong> scheduled for {event_date}.</p>
            
            <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p>Your event has been submitted and is currently <strong>awaiting admin approval</strong>. You will receive another email once your event has been reviewed.</p>
            </div>
            
            <p>While waiting for approval, you can make any necessary preparations for your event.</p>
            
            <p>Thank you for using AUP Events!</p>
            
            <p style="margin-top: 20px; font-size: 14px; color: #666;">Best regards,<br>AUP Events System</p>
        </div>
        """
        
        return self.send_email(to_email, subject, text=text, html=html)
        
    def send_event_approval_confirmation(self, to_email, event_name, is_approved, rejection_reason=None):
        """Send notification to event creator about event approval status"""
        
        if is_approved:
            subject = f"✅ Event Approved: {event_name}"
            
            text = f"""
            Hello,
            
            Great news! Your event "{event_name}" has been approved and is now live on AUP Events.
            
            Users can now see your event and register for it.
            
            Thank you,
            AUP Events System
            """
            
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                <h2 style="color: #4F46E5; text-align: center;">Event Approved!</h2>
                
                <div style="text-align: center; margin: 20px 0;">
                    <span style="font-size: 48px;">✅</span>
                </div>
                
                <p>Hello,</p>
                
                <p>Great news! Your event <strong>"{event_name}"</strong> has been approved and is now live on AUP Events.</p>
                
                <p>Users can now see your event and register for it.</p>
                
                <p style="margin-top: 20px; font-size: 14px; color: #666;">Thank you,<br>AUP Events System</p>
            </div>
            """
        else:
            subject = f"❌ Event Rejected: {event_name}"
            
            reason_text = f"\nReason: {rejection_reason}" if rejection_reason else ""
            reason_html = f"<p><strong>Reason:</strong> {rejection_reason}</p>" if rejection_reason else ""
            
            text = f"""
            Hello,
            
            We regret to inform you that your event "{event_name}" has been rejected.{reason_text}
            
            If you have any questions, please contact the administrator.
            
            Thank you,
            AUP Events System
            """
            
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                <h2 style="color: #DC2626; text-align: center;">Event Rejected</h2>
                
                <div style="text-align: center; margin: 20px 0;">
                    <span style="font-size: 48px;">❌</span>
                </div>
                
                <p>Hello,</p>
                
                <p>We regret to inform you that your event <strong>"{event_name}"</strong> has been rejected.</p>
                
                {reason_html}
                
                <p>If you have any questions, please contact the administrator.</p>
                
                <p style="margin-top: 20px; font-size: 14px; color: #666;">Thank you,<br>AUP Events System</p>
            </div>
            """
        
        return self.send_email(to_email, subject, text=text, html=html)


