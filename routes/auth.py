from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager, limiter, csrf
from database.models import User, EmployeeProfile, AuditLog, BlockedIP, LoginToken, OfficeSettings, VerificationToken
from utils.email_service import send_otp_email
from utils.time_utils import get_nepal_time
from datetime import datetime, timedelta
import random
import string
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from utils.location_utils import calculate_distance
from utils.security_utils import validate_password_strength
from utils import location_service

auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

@auth_bp.route('/qr-login/<token>', methods=['GET', 'POST'])
def qr_login(token):
    if current_user.is_authenticated:
        flash('Please logout first.', 'warning')
        return redirect(url_for('auth.login'))

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = serializer.loads(token, salt=current_app.config['QR_LOGIN_SALT'], max_age=300)
    except SignatureExpired:
        flash('QR token expired. Please scan again.', 'danger')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Invalid QR token.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user or not user.is_active:
        flash('Invalid user or inactive account.', 'danger')
        return redirect(url_for('auth.login'))

    # STAFF: Direct Login (QR Login Bypass)
    if user.role != 'admin':
        # SUCCESS (Phase 1): Instant Login for Staff/Interns/Students with consistent tokens
        import secrets
        token = secrets.token_hex(16)
        user.current_session_id = token
        session['session_token'] = token
        
        login_user(user)
        session['session_version'] = current_app.config.get('BOOT_ID')
    else:
        # ADMIN: Security check required
        # For Admin QR, we still require a password check (Hybrid Security)
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps(user.id, salt=current_app.config['QR_LOGIN_SALT'])
        return redirect(url_for('auth.qr_password_check', token=token))
    
    db.session.commit()
    flash('Logged in via QR code successfully.', 'success')
    return redirect(url_for('staff.dashboard'))

@auth_bp.route('/qr-password-check/<token>', methods=['GET', 'POST'])
def qr_password_check(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = serializer.loads(token, salt=current_app.config['QR_LOGIN_SALT'], max_age=300)
    except (SignatureExpired, BadSignature):
        flash('Invalid or expired QR token.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user or user.role != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password')
        if check_password_hash(user.password_hash, password):
            import secrets
            token = secrets.token_hex(16)
            user.current_session_id = token
            session['session_token'] = token
            
            login_user(user)
            db.session.add(AuditLog(user_id=user.id, action="Admin identity verified via QR + Password", ip_address=request.remote_addr))
            db.session.commit()
            flash('Admin QR Login Successful.', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid password.', 'danger')

    return render_template('auth/qr_password_check.html', token=token, user=user)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", error_message="Security: Too many login attempts from this IP.")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard' if current_user.role == 'admin' else 'staff.dashboard'))
    
    ip = request.remote_addr
    now = get_nepal_time()
    block = BlockedIP.query.filter_by(ip_address=ip).first()
    
    # Check if a block is currently active (within the lockout window)
    if block and block.blocked_until and block.blocked_until > now:
        wait_seconds = int((block.blocked_until - now).total_seconds())
        if wait_seconds >= 3600:
            time_str = f"{wait_seconds // 3600}h { (wait_seconds % 3600) // 60 }m"
        elif wait_seconds >= 60:
            time_str = f"{wait_seconds // 60}m {wait_seconds % 60}s"
        else:
            time_str = f"{wait_seconds}s"
            
        flash(f'Security Lockout: Your IP is temporarily blocked. Try again in {time_str}.', 'danger')
        return render_template('auth/login.html', selected_role=request.form.get('role', 'admin'))
    
    if request.method == 'POST':
        # Auto-trim and normalize email/password
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        
        # Security: Hybrid Email Domain Validation (Regex-based restoration)
        import re
        role_selected = request.form.get('role', 'admin')
        domain_pattern = r'^[a-zA-Z0-9._%+-]+@ems\.com$'
        if not re.match(domain_pattern, email):
             flash('Security Alert: Access is restricted to official @ems.com domains.', 'danger')
             return render_template('auth/login.html', selected_role=role_selected)
        
        if not email:
            flash('Email is required.', 'danger')
            return render_template('auth/login.html', selected_role=request.form.get('role', 'admin'))
            
        # Look up user by Email OR Employee ID
        user = User.query.filter_by(email=email).first()
        if not user:
            # Fallback search by Employee ID (case-insensitive)
            user = User.query.join(EmployeeProfile).filter(
                db.func.lower(EmployeeProfile.employee_id) == email.lower()
            ).first()
        
        if user:
            is_valid = check_password_hash(user.password_hash, password)
            if is_valid:
                # SUCCESS (Phase 1): Trigger OTP Flow
                # Note: We now ignore the raw selected_role tab and use the user's actual role
                # This fixes the "Identity Error" friction for Students/Interns.
                selected_role = user.role
                
                # IMPORTANT: Reset lockout attempts immediately upon correct password
                if block:
                    db.session.delete(block)
                    db.session.commit()
                    block = None # Clear local variable

                # Security: Check if account is active
                if not user.is_active:
                    flash('Account Inactive: Please contact the administrator.', 'danger')
                    return render_template('auth/login.html', selected_role=selected_role)

                # SUCCESS (Phase 1): Trigger OTP Flow
                otp = generate_otp()
                user.otp = otp
                user.otp_expiry = get_nepal_time() + timedelta(minutes=10)
                db.session.add(AuditLog(user_id=user.id, action="Login Phase 1 Success (OTP Sent)", ip_address=ip))
                db.session.commit()
                
                # Send OTP via email and display in console for dev
                send_otp_email(user, otp)
                print("\n" + "="*50)
                print(f"║ LOGIN FOR: {user.email}")
                print(f"║ OTP CODE:  \033[1;92m{otp}\033[0m")
                print("="*50 + "\n")
                
                session['pending_user_id'] = user.id
                flash('Two-Factor Authentication: A security code has been sent to your email.', 'info')
                return redirect(url_for('auth.verify_otp'))
            else:
                current_app.logger.warning(f"Login failed: Password mismatch for {email}")
                flash("Invalid email or password.", "danger")
        else:
            current_app.logger.warning(f"Login failed: User not found - {email}")
            flash("Invalid email or password.", "danger")

        # failure handling (Graduated Lockout Policy)
        if not block:
            block = BlockedIP(ip_address=ip, attempts=1, stage=0, reason="Failed login")
            db.session.add(block)
        else:
            # Grace Period Reset: If the last failure was over an hour ago, reset stages
            if block.last_attempt_at and (get_nepal_time() - block.last_attempt_at).total_seconds() > 3600:
                block.attempts = 1
                block.stage = 0
            else:
                block.attempts += 1
            block.last_attempt_at = get_nepal_time()

        # Define stages: Stage 0-4
        stages = {
            0: {'max': 5, 'duration': 60},     # 1 min (Increased from 3 to 5)
            1: {'max': 2, 'duration': 300},    # 5 min (Increased from 1 to 2)
            2: {'max': 3, 'duration': 600},    # 10 min
            3: {'max': 2, 'duration': 1800},   # 30 min (Increased from 1 to 2)
            4: {'max': 3, 'duration': 86400}   # 24 hours
        }
        
        current_stage = stages.get(block.stage, stages[4])
        
        if block.attempts >= current_stage['max']:
            lock_duration = current_stage['duration']
            block.blocked_until = get_nepal_time() + timedelta(seconds=lock_duration)
            block.attempts = 0
            block.stage = min(block.stage + 1, 4)
            
            if lock_duration >= 86400:
                time_str = "24 hours"
            elif lock_duration >= 1800:
                time_str = f"{lock_duration // 60} minutes"
            else:
                time_str = f"{lock_duration // 60} minute(s)"
                
            msg = f"Too many failed attempts. Security Lockout: Your IP is blocked for {time_str}."
        else:
            remaining = current_stage['max'] - block.attempts
            msg = f"Invalid email or password. {remaining} attempt(s) remaining before lockout."
        
        db.session.commit()
        flash(msg, 'danger')
        return render_template('auth/login.html', selected_role=request.form.get('role', 'admin'))

    return render_template('auth/login.html')



@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    ip = request.remote_addr
    block = BlockedIP.query.filter_by(ip_address=ip).first()
    
    if block and block.blocked_until and block.blocked_until > get_nepal_time():
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        if user.otp == entered_otp and user.otp_expiry > get_nepal_time():
            # SUCCESS
            user.otp = None
            user.otp_expiry = None
            if block: db.session.delete(block)
            
            # Generate session hardware-binding token
            token = secrets.token_hex(16)
            user.current_session_id = token
            session['session_token'] = token
            
            login_user(user)
            session['session_version'] = current_app.config.get('BOOT_ID')
            session.permanent = True # Enable 24-hour location re-verification policy
            session.pop('pending_user_id', None)
            
            db.session.add(AuditLog(user_id=user.id, action="Login", ip_address=ip))
            db.session.commit()
            
            return redirect(url_for('admin.dashboard' if user.role == 'admin' else 'staff.dashboard'))
        else:
            if not block:
                block = BlockedIP(ip_address=ip, attempts=1, reason="OTP failure")
                db.session.add(block)
            else:
                block.attempts += 1
            
            if block.attempts >= 6:
                block.blocked_until = get_nepal_time() + timedelta(days=3650)
            elif block.attempts >= 3:
                block.blocked_until = get_nepal_time() + timedelta(minutes=30)
            
            db.session.commit()
            flash('Invalid or expired OTP.', 'danger')
            if block.blocked_until: return redirect(url_for('auth.login'))
            
    return render_template('auth/otp.html')

@auth_bp.route('/resend-otp')
@limiter.limit("5 per hour")
def resend_otp():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('auth.login'))
        
    otp = generate_otp()
    user.otp = otp
    user.otp_expiry = get_nepal_time() + timedelta(minutes=10)
    db.session.commit()
    
    send_otp_email(user, otp)
    print("\n" + "="*50)
    print(f"║ RESENT FOR: {user.email}")
    print(f"║ NEW OTP:    \033[1;92m{otp}\033[0m")
    print("="*50 + "\n")
    
    flash('A new OTP has been sent to your email.', 'info')
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/logout')
@login_required
def logout():
    audit = AuditLog(user_id=current_user.id, action="Logout", ip_address=request.remote_addr)
    db.session.add(audit)
    db.session.commit()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

from utils.email_service import send_otp_email, send_password_reset_email

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Re-enforced Personal Email Requirement (Hybrid Security)
            profile = EmployeeProfile.query.filter_by(user_id=user.id).first()
            if not profile or not profile.personal_email:
                db.session.add(AuditLog(user_id=user.id, action="Failed Password Reset (No Personal Email)", ip_address=request.remote_addr))
                db.session.commit()
                flash('Security Violation: Your account has no verified recovery email. Contact Admin.', 'danger')
                return redirect(url_for('auth.login'))

            otp = generate_otp()
            user.otp = otp
            user.otp_expiry = get_nepal_time() + timedelta(minutes=15)
            db.session.commit()
            
            # Hybrid: Send to personal email for security
            send_otp_email(user, otp, recipient=profile.personal_email)
            
            print("\n" + "="*50)
            print(f"║ PASSWORD RESET FOR: {user.email}")
            print(f"║ SENT TO PERSONAL:   {profile.personal_email}")
            print(f"║ OTP CODE:           \033[1;96m{otp}\033[0m")
            print("="*50 + "\n")
            
        # Privacy Hardening: Always show the same success message to prevent email guessing
        session['reset_email'] = email
        flash('If an account is associated with that email, a code has been sent to your registered email.', 'info')
        return redirect(url_for('auth.verify_reset_otp'))
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/verify-reset-otp', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def verify_reset_otp():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        user = User.query.filter_by(email=email).first()
        
        if user and user.otp == otp and user.otp_expiry and user.otp_expiry > get_nepal_time():
            session['reset_otp_verified'] = True
            flash('OTP Verified. Please set your new password.', 'success')
            return redirect(url_for('auth.reset_password'))
        else:
            flash('Invalid or expired OTP.', 'danger')
            
    return render_template('auth/verify_reset_otp.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def reset_password():
    email = session.get('reset_email')
    if not email or not session.get('reset_otp_verified'):
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html')
            
        user = User.query.filter_by(email=email).first()
        if user:
            # Security: Backend Strength Validation
            is_valid, msg = validate_password_strength(new_password)
            if not is_valid:
                flash(msg, 'danger')
                return render_template('auth/reset_password.html')
                
            user.password_hash = generate_password_hash(new_password)
            user.otp = None
            user.otp_expiry = None
            
            # Log the change
            db.session.add(AuditLog(
                user_id=user.id,
                action='password-reset',
                details=f'Password reset successfully via OTP for {email}',
                ip_address=request.remote_addr
            ))
            
            db.session.commit()
            session.pop('reset_email', None)
            session.pop('reset_otp_verified', None)
            flash('Password reset successful. Please login with your new credentials.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Error resetting password.', 'danger')
            
    return render_template('auth/reset_password.html')

