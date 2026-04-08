import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from extensions import db, login_manager, mail, migrate, limiter, csrf
from flask_wtf.csrf import CSRFError
from flask_talisman import Talisman
from config import config
import threading

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure database directory exists
    db_dir = os.path.join(app.root_path, 'database')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    csrf.init_app(app)

    # Initialize Talisman (Security Headers & CSP)
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            'https://cdn.tailwindcss.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com',
            'https://unpkg.com', # Whitelist QR scanner library
            "'unsafe-eval'", # Required for Alpine.js and Tailwind CDN
            "'unsafe-inline'" # Required for inline scripts in base.html
        ],
        'style-src': [
            "'self'",
            'https://cdn.tailwindcss.com',
            'https://fonts.googleapis.com',
            "'unsafe-inline'" # Required for Tailwinds and inline styles
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'data:'
        ],
        'connect-src': ["'self'"], # Allow relative API calls
        'img-src': [
            "'self'",
            'data:',
            'https://via.placeholder.com',
            'https:'
        ],
    }
    
    Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        force_https=app.config.get('SESSION_COOKIE_SECURE', False), # Only force HTTPS if secure cookies are enabled
        session_cookie_secure=app.config.get('SESSION_COOKIE_SECURE', False),
        session_cookie_http_only=True,
        session_cookie_samesite='Lax'
    )

    # Logging Configuration
    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/ems.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('EMS startup')


    from middleware import setup_middleware
    setup_middleware(app)
    
    # Fix for ngrok HTTPS reverse proxy
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    except ImportError:
        app.logger.warning("ProxyFix middleware not found. IP tracking might be inaccurate behind proxies.")

    # Import and register Blueprints
    from routes.auth import auth_bp
    from routes.admin_routes import admin_bp
    from routes.staff import staff_bp
    from routes.contact_routes import contact_bp
    from routes.qr_routes import qr_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/dashboard')
    app.register_blueprint(contact_bp, url_prefix='/contact')
    app.register_blueprint(qr_bp, url_prefix='/qr')

    # Security: Use a stable SESSION_VERSION to prevent forced logouts on dev refreshes.
    # The session only invalidates if the admin manually changes SESSION_VERSION in config.
    app.config['BOOT_ID'] = app.config.get('SESSION_VERSION', '1')


    # Global Session Reset Hook (Auto Logout on Server Restart/Refresh)
    @app.before_request
    def check_session_version():
        from flask_login import current_user, logout_user
        from flask import session, flash, redirect, url_for
        
        # We only check authenticated users
        if current_user.is_authenticated:
            boot_id = app.config.get('BOOT_ID')
            user_session_version = session.get('session_version')
            
            # Strict Enforcement: Logout if version mismatch (forced logout on restart)
            if user_session_version != boot_id:
                app.logger.info(f"Session security mismatch. Boot ID changed. Force Logout User {current_user.id}.")
                logout_user()
                session.clear()
                flash('Security Alert: Your session has been reset due to a server refresh. Please log in again.', 'warning')
                return redirect(url_for('auth.login'))

    # Context processor for global variables
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        import pytz
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        offset = datetime.now(nepal_tz).strftime('%z')
        # Format as "+05:45" for JavaScript ISO strings
        tz_offset = offset[:3] + ':' + offset[3:]
        return {
            'tz_offset': tz_offset,
            'BOOT_ID': app.config.get('BOOT_ID'),
            'REQUIRE_LOCATION_VERIFICATION': app.config.get('REQUIRE_LOCATION_VERIFICATION', False)
        }

    @app.route('/')
    @app.route('/login')
    def index():
        return redirect(url_for('auth.login'))

    # Background Monitoring Thread
    def start_monitoring():
        from utils.attendance_service import AttendanceMonitor
        monitor = AttendanceMonitor(app)
        monitor.run()

    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Start monitoring thread as a daemon
        monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
        monitor_thread.start()

    # Centralized Error Handling
    @app.errorhandler(403)
    def forbidden(e):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or 'json' in request.accept_mimetypes.values():
            return jsonify({'success': False, 'message': 'Permission Denied: ' + str(e.description)}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"CSRF Error: {e.description}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': 'Session expired. Please refresh the page.'}), 400
        flash('Your session has expired for security. Please try again.', 'warning')
        return render_template('errors/400.html', error_message='Session expired. Please refresh the page.'), 400

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def internal_server_error(e):
        # In Debug mode, let the default Flask interactive debugger handle it
        if app.debug:
            raise e
            
        app.logger.error(f"Server Error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': 'System temporary unavailable. Please try again later.'}), 500
        return render_template('errors/500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app('development')
    app.run(host='127.0.0.1', port=5000, debug=True)

