from flask import request, abort, flash, redirect, url_for, session
from flask_login import current_user, logout_user
from extensions import db
from database.models import BlockedIP
from utils.time_utils import get_nepal_time

def setup_middleware(app):
    @app.before_request
    def check_security():
        # 1. IP Block Check
        ip = request.remote_addr
        now = get_nepal_time()
        blocked = BlockedIP.query.filter_by(ip_address=ip).first()
        if blocked and blocked.blocked_until and blocked.blocked_until > now:
            wait_seconds = int((blocked.blocked_until - now).total_seconds())
            if wait_seconds >= 3600:
                time_str = f"{wait_seconds // 3600}h { (wait_seconds % 3600) // 60 }m"
            elif wait_seconds >= 60:
                time_str = f"{wait_seconds // 60}m {wait_seconds % 60}s"
            else:
                time_str = f"{wait_seconds}s"
            
            # If it's a regular request, redirect to login with the message
            # If it's the login page itself, let auth.py handle the flash
            if request.endpoint != 'auth.login':
                abort(403, description=f"Security Lockout: Your IP is temporarily blocked. Try again in {time_str}.")

        # 2. Single Session Enforcement
        if current_user.is_authenticated:
            # Skip check for static files and logout route
            if request.endpoint and 'static' not in request.endpoint and 'auth.logout' not in request.endpoint:
                # Bypass single session enforcement for admins
                if current_user.role != 'admin':
                    stored_session = current_user.current_session_id
                    current_session = session.get('session_token')
                    
                    if stored_session and stored_session != current_session:
                        logout_user()
                        session.clear()
                        flash('You have been logged out because your account was logged in from another device.', 'warning')
                        return redirect(url_for('auth.login'))

    @app.after_request
    def add_security_headers(response):
        # Additional headers not handled by Talisman if any
        # Talisman handled: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP, HSTS
        return response
