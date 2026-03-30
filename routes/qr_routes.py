from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, csrf
from database.models import User, EmployeeProfile, LoginLog, AuditLog
from utils.time_utils import get_nepal_time
from datetime import datetime, timedelta
import os
from utils import location_service

qr_bp = Blueprint('qr', __name__)

# ─── Location Verification API (New) ──────────────────────────────────────────

@qr_bp.route('/api/grant-bypass/<int:user_id>', methods=['POST'])
@login_required
def grant_bypass(user_id):
    """Admin endpoint to grant a 24-hour location bypass to a specific user"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    user.location_bypass_until = datetime.now() + timedelta(hours=24)
    
    # Audit Log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Granted 24h Location Bypass to {user.email}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'24h bypass granted to {user.email}'})

@qr_bp.route('/api/check-bypass-status', methods=['POST'])
@csrf.exempt
def check_bypass_status():
    """Public endpoint to check if an email currently has a location bypass"""
    data = request.get_json()
    email = data.get('email')
    portal_role = data.get('role') # The role currently selected in the UI
    
    # 1. Office IP Bypass (Role-Agnostic, checked first)
    from database.models import OfficeSettings
    settings = OfficeSettings.query.first()
    office_ip = settings.office_ip if settings and settings.office_ip else current_app.config.get('OFFICE_PUBLIC_IP', '')
    if office_ip and request.remote_addr == office_ip:
        return jsonify({'has_bypass': True, 'reason': 'office_ip'})
        
    # 2. User-Specific Bypasses (Require Email)
    if not email:
        return jsonify({'has_bypass': False})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'has_bypass': False})
    
    # Admins are exempt by default, but only if they are in the Admin Portal
    if user.role == 'admin' and portal_role == 'admin':
        return jsonify({'has_bypass': True, 'reason': 'admin'})
        
    # Check for temporary bypass
    if user.location_bypass_until and user.location_bypass_until > datetime.now():
        return jsonify({'has_bypass': True, 'reason': 'temporary'})
        
    return jsonify({'has_bypass': False})

@qr_bp.route('/api/generate-loc-token', methods=['POST'])
@csrf.exempt
def generate_loc_token():
    """Generates a unique token for location verification"""
    token = location_service.generate_location_token()
    
    # Generate the mobile verification URL
    external_url = os.environ.get('EXTERNAL_URL')
    if external_url:
        # Force HTTPS and handle prefix correctly
        base_url = external_url.rstrip('/').replace('http://', 'https://')
        verify_url = base_url + url_for('qr.verify_location_page', token=token)
    else:
        # Default fallback
        verify_url = url_for('qr.verify_location_page', token=token, _external=True, _scheme='https')
        if 'http://' in verify_url:
            verify_url = verify_url.replace('http://', 'https://')
        
    return jsonify({
        'success': True,
        'token': token,
        'verify_url': verify_url
    })

@qr_bp.route('/verify-location/<token>')
def verify_location_page(token):
    """Mobile landing page for GPS verification"""
    status = location_service.check_token_status(token)
    if status == 'expired':
        return render_template('qr/verify_location.html', error="Token expired. Please scan a new QR code.")
    return render_template('qr/verify_location.html', token=token)

@qr_bp.route('/api/submit-location', methods=['POST'])
@csrf.exempt
def submit_location():
    """Receives GPS coordinates from mobile device"""
    data = request.get_json()
    token = data.get('token')
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if not token:
        return jsonify({'success': False, 'message': 'Missing token'}), 400
        
    from database.models import OfficeSettings
    settings = OfficeSettings.query.first()
    
    # Check IP fallback first (High Security)
    user_ip = request.remote_addr
    office_ip = settings.office_ip if settings and settings.office_ip else current_app.config.get('OFFICE_PUBLIC_IP', '')
    
    # If the user is on the Office Network, verify immediately
    if location_service.verify_ip_fallback(token, user_ip, office_ip):
        return jsonify({'success': True, 'message': 'Location verified via Office Network.'})
    
    # If not on Office IP, we MUST have GPS coordinates
    if lat is None or lon is None:
        msg = f"GPS denied and not on Office Network. (Your IP: {user_ip})"
        return jsonify({'success': False, 'message': msg}), 403
    
    # Otherwise, check GPS distance
    office_lat = settings.latitude if settings else current_app.config.get('OFFICE_LATITUDE')
    office_lon = settings.longitude if settings else current_app.config.get('OFFICE_LONGITUDE')
    radius = settings.radius if settings else current_app.config.get('GEOFENCE_RADIUS', 100)
    
    success, message = location_service.verify_token_location(token, lat, lon)
    return jsonify({'success': success, 'message': message})

@qr_bp.route('/api/check-loc-status/<token>')
def check_loc_status(token):
    """Polling endpoint for PC to check if mobile verification is done"""
    status = location_service.check_token_status(token)
    return jsonify({'status': status})

# ─── Badge Generation Routes ──────────────────────────────────────────────────

def generate_qr_url(user):
    from itsdangerous import URLSafeSerializer
    import os
    from flask import current_app, url_for
    
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    token_data = {
        "username": user.profile.full_name if user.profile else user.username,
        "user_id": user.profile.employee_id if user.profile else user.id,
        "role": user.role
    }
    token = s.dumps(token_data)
    
    external_url = os.environ.get('EXTERNAL_URL')
    if external_url:
        return external_url.rstrip('/') + url_for('qr.auto_login', token=token)
    return url_for('qr.auto_login', token=token, _external=True)

@qr_bp.route('/generate/employee/<int:user_id>')
@login_required
def em_qr_gen(user_id):
    if current_user.role != 'admin' and current_user.id != user_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('staff.dashboard'))
    user = User.query.get_or_404(user_id)
    verify_url = generate_qr_url(user)
    return render_template('qr/em_qr_gen.html', user=user, verify_url=verify_url)

@qr_bp.route('/generate/intern/<int:user_id>')
@login_required
def int_qr_gen(user_id):
    if current_user.role != 'admin' and current_user.id != user_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('staff.dashboard'))
    user = User.query.get_or_404(user_id)
    verify_url = generate_qr_url(user)
    return render_template('qr/int_qr_gen.html', user=user, verify_url=verify_url)

@qr_bp.route('/generate/student/<int:user_id>')
@login_required
def std_qr_gen(user_id):
    if current_user.role != 'admin' and current_user.id != user_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('staff.dashboard'))
    user = User.query.get_or_404(user_id)
    verify_url = generate_qr_url(user)
    return render_template('qr/std_qr_gen.html', user=user, verify_url=verify_url)

# ─── Scanner Page ─────────────────────────────────────────────────────────────

@qr_bp.route('/scan')
def scanner():
    return render_template('qr/qr_scan.html')

# ─── Login API ────────────────────────────────────────────────────────────────

@qr_bp.route('/api/qr-login', methods=['POST'])
def qr_login_api():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data received'}), 400
        
    username = data.get('username')
    user_id_badge = data.get('user_id')
    role = data.get('role')
    lat = data.get('latitude')
    lon = data.get('longitude')
    token = data.get('token')
    
    # Handle Token-based login (new URL method)
    if token:
        from itsdangerous import URLSafeSerializer, BadSignature
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        try:
            token_data = s.loads(token)
            username = token_data.get('username')
            user_id_badge = token_data.get('user_id')
            role = token_data.get('role')
        except BadSignature:
            current_app.logger.warning("QR Login: Invalid token signature.")
            return jsonify({'success': False, 'message': 'Invalid QR token.'}), 403
            
    if not username or not user_id_badge or not role:
        return jsonify({'success': False, 'message': 'Missing user data in request.'}), 400
    
    # 1. Validate user exists in database
    # Search by employee_id primarily, but also check full_name match
    user = User.query.join(EmployeeProfile).filter(
        EmployeeProfile.employee_id == user_id_badge,
        User.role == role
    ).first()
    
    # Validation check: Ensure the badge name matches the database profile name (case-insensitive)
    if user:
        db_name = user.profile.full_name.strip().lower()
        badge_name = username.strip().lower()
        if db_name != badge_name:
            current_app.logger.warning(f"QR Login: Name Mismatch for {user_id_badge}. Badge says '{username}', DB says '{user.profile.full_name}'")
            return jsonify({'success': False, 'message': 'Badge name mismatch.'}), 403
    
    if not user:
        current_app.logger.error(f"QR Login: User not found. ID: {user_id_badge}, Name: {username}, Role: {role}")
        return jsonify({'success': False, 'message': 'User not found or role mismatch.'}), 404
        
    if not user.is_active:
        return jsonify({'success': False, 'message': 'Account is inactive.'}), 403

    # 2. Store login record
    log = LoginLog(
        username=username,
        user_id=user_id_badge,
        role=role,
        latitude=lat,
        longitude=lon,
        login_time=get_nepal_time()
    )
    db.session.add(log)
    
    # 3. Create user session
    login_user(user)
    
    # Audit Log for QR Login
    db.session.add(AuditLog(
        user_id=user.id,
        action="User logged in via QR Badge Scan",
        details=f"Device IP: {request.remote_addr}, Lat: {lat}, Lon: {lon}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    # 4. Return redirect URL based on role
    # Mapping to standard dashboard routes but including the requested virtual paths
    redirect_map = {
        'employee': url_for('staff.dashboard'),
        'intern': url_for('staff.dashboard'),
        'student': url_for('staff.dashboard')
    }
    
    return jsonify({
        'success': True, 
        'message': 'Login successful',
        'redirect_url': redirect_map.get(role, url_for('staff.dashboard'))
    })

# ─── Virtual Redirect Routes (to satisfy requirement 4) ───────────────────────

@qr_bp.route('/employee_dashboard.html')
@login_required
def employee_dashboard_virtual():
    return redirect(url_for('staff.dashboard'))

@qr_bp.route('/intern_dashboard.html')
@login_required
def intern_dashboard_virtual():
    return redirect(url_for('staff.dashboard'))

@qr_bp.route('/student_dashboard.html')
@login_required
def student_dashboard_virtual():
    return redirect(url_for('staff.dashboard'))

# ─── Auto-Login from Native Camera QR Scan ────────────────────────────────────

@qr_bp.route('/auto-login/<token>')
def auto_login(token):
    from itsdangerous import URLSafeSerializer, BadSignature
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    try:
        # Validate token early before rendering template
        token_data = s.loads(token)
    except BadSignature:
        flash('Invalid or expired QR code badge.', 'danger')
        return redirect(url_for('auth.login'))
        
    return render_template('qr/auto_login.html', token=token, user_info=token_data)
