import logging
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
import requests
from flask import request, g
from config import Config

class DatadogLogger:
    def __init__(self):
        self.api_key = Config.DATADOG_API_KEY
        self.url = Config.DATADOG_INTAKE_URL
        self.service = "amity-events-service"
        self.env = Config.ENV

    def _send_log(self, log_data):
        headers = {
            'Content-Type': 'application/json',
            'DD-API-KEY': self.api_key
        }
        
        base_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': self.service,
            'env': self.env,
            'host': request.host if request else 'unknown'
        }
        
        # Merge base data with log data
        log_entry = {**base_data, **log_data}
        
        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=[log_entry],
                timeout=1  # Short timeout to not block the application
            )
            return response.status_code == 202
        except Exception:
            return False

    def log_request(self):
        """Log incoming request details"""
        g.request_start_time = datetime.now(timezone.utc)
        
        log_data = {
            'type': 'request',
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.args),
            'headers': dict(request.headers),
            'source_ip': request.remote_addr,
            'user_agent': request.user_agent.string
        }
        
        self._send_log(log_data)

    def log_response(self, response):
        """Log response details"""
        duration = None
        if hasattr(g, 'request_start_time'):
            duration = (datetime.now(timezone.utc) - g.request_start_time).total_seconds()
        
        log_data = {
            'type': 'response',
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': duration,
            'response_size': len(response.get_data())
        }
        
        self._send_log(log_data)
        return response

    def log_error(self, error):
        """Log error details"""
        log_data = {
            'type': 'error',
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'method': request.method,
            'path': request.path,
            'traceback': traceback.format_exc()
        }
        
        self._send_log(log_data)

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now(timezone.utc)
        
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Log successful execution
            log_data = {
                'type': 'performance',
                'function': func.__name__,
                'duration': duration,
                'status': 'success'
            }
            
            DatadogLogger()._send_log(log_data)
            return result
            
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Log failed execution
            log_data = {
                'type': 'performance',
                'function': func.__name__,
                'duration': duration,
                'status': 'error',
                'error_type': e.__class__.__name__,
                'error_message': str(e)
            }
            
            DatadogLogger()._send_log(log_data)
            raise
            
    return wrapper 