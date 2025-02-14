from flask import request, abort, make_response, session
import secrets
import hashlib
import time

class CSRFProtection:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _generate_token(self):
        """Generate a new CSRF token"""
        token = secrets.token_hex(32)
        # Store token hash in session
        session['csrf_token'] = hashlib.sha256(token.encode()).hexdigest()
        session['csrf_time'] = time.time()
        return token

    def _verify_token(self, token):
        """Verify the CSRF token"""
        if not token or 'csrf_token' not in session:
            return False
        
        # Check token expiration (30 minutes)
        if time.time() - session.get('csrf_time', 0) > 1800:
            return False
            
        expected = session['csrf_token']
        actual = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(actual, expected)

    def _before_request(self):
        """Check CSRF token before processing request"""
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = request.headers.get('X-CSRF-Token')
            if not self._verify_token(token):
                abort(403, description="Invalid or missing CSRF token")

    def _after_request(self, response):
        """Add new CSRF token to response"""
        if 'csrf_token' not in session:
            token = self._generate_token()
            response.headers['X-CSRF-Token'] = token
        return response 