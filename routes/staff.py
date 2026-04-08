from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, session
from flask_login import login_required, current_user
from extensions import db
from database.models import Attendance, LeaveRequest, EmployeeProfile, Notice, TimeLog
from utils.time_utils import get_nepal_time
from utils.attendance_service import AttendanceService
from utils.qr_service import QRService
from database.models import Payroll
from datetime import datetime, timedelta

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/dashboard')
@login_required
def dashboard():
    today = get_nepal_time().date()
    
    today_str = today.strftime('%Y-%m-%d')
    
    attendance = Attendance.query.filter_by(user_id=current_user.id).filter(db.func.date(Attendance.check_in) == today).first()
    leaves = LeaveRequest.query.filter_by(user_id=current_user.id).limit(5).all()
    
    # Fetch Notices
    cutoff_date = get_nepal_time() - timedelta(days=30)
    notices = Notice.query.filter(
        Notice.is_active == True,
        Notice.created_at >= cutoff_date,
        db.or_(
            Notice.role_restriction == 'all', 
            Notice.role_restriction == current_user.role,
            Notice.target_user_id == current_user.id
        )
    ).order_by(Notice.created_at.desc()).limit(5).all()
    
    # Smart Popup Logic
    latest_notice = notices[0] if notices else None
    show_notice_popup = False
    if latest_notice:
        now_dt = get_nepal_time()
        time_diff = (now_dt - latest_notice.created_at).total_seconds()
        is_recent = time_diff < 86400  # 24 hours
        already_seen = session.get(f'notice_seen_{latest_notice.id}', False)
        if is_recent and not already_seen:
            show_notice_popup = True
            session[f'notice_seen_{latest_notice.id}'] = True
    
    qr_path = QRService.generate_employee_badge(current_user.id)

    # PRE-LOAD STATS FOR ULTRA-FAST INITIAL RENDERING
    from utils.leave_service import LeaveService
    profile = current_user.profile
    annual_allowance = profile.leave_allowance if profile else 15.0
    
    initial_stats = {
        'attendance_score': AttendanceService.calculate_attendance_score(current_user.id, today),
        'leave_balance': LeaveService.calculate_leave_balance(current_user.id, annual_allowance),
        'workshop_status': profile.workshop_status if profile else 'Ongoing',
        'payment_status': profile.payment_status if profile else 'Pending'
    }
    
    return render_template('employee/dashboard.html', 
                           attendance=attendance, 
                           leaves=leaves, 
                           qr_path=qr_path, 
                           notices=notices,
                           latest_notice=latest_notice,
                           show_notice_popup=show_notice_popup,
                           today_date=today,
                           initial_stats=initial_stats)

@staff_bp.route('/api/attendance-stats', methods=['GET'])
@login_required
def get_attendance_stats():
    """
    Asynchronous endpoint to fetch dashboard statistics without blocking page load.
    """
    today = get_nepal_time().date()
    today_str = today.strftime('%Y-%m-%d')
    
    # Auto-sync past 30 days and next 7 days for Saturdays (Moved to async stats API to prevent UI blocking)
    if session.get('last_saturday_sync') != today_str:
        try:
            AttendanceService.sync_saturdays_for_period(current_user.id, today - timedelta(days=30), today + timedelta(days=7))
            session['last_saturday_sync'] = today_str
        except Exception as e:
            current_app.logger.error(f"Saturday sync error: {e}")

    # Calculate Attendance Score
    attendance_score = AttendanceService.calculate_attendance_score(current_user.id, today)
    
    # Calculate dynamic leave balance
    from utils.leave_service import LeaveService
    profile = current_user.profile
    annual_allowance = profile.leave_allowance if profile else 15.0
    workshop_status = profile.workshop_status if profile else 'Ongoing'
    payment_status = profile.payment_status if profile else 'Pending'
    
    leave_balance = LeaveService.calculate_leave_balance(current_user.id, annual_allowance)
    
    return jsonify({
        'attendance_score': attendance_score,
        'leave_balance': leave_balance,
        'workshop_status': workshop_status,
        'payment_status': payment_status,
        'has_profile': profile is not None
    })

@staff_bp.route('/check-in', methods=['POST'])
@login_required
def check_in():
    # Day-based Check-In Logic: Prevent duplicate attendance records for the same day
    from database.models import AuditLog, OfficeSettings, AllowedLocation
    today = get_nepal_time().date()
    
    # Check for any attendance record today (active or completed)
    existing = Attendance.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Attendance.check_in) == today
    ).first()
    
    if existing:
        # User already has an attendance record today
        db.session.add(AuditLog(
            user_id=current_user.id, 
            action=f"Duplicate check-in attempt (Already attending)", 
            ip_address=request.remote_addr
        ))
        db.session.commit()
        return jsonify({'success': False, 'message': 'You have already checked in for today.'}), 400

    # GPS Location Verification (REMOVED: Location access feature disabled)
    # data = request.get_json() or {}
    # lat = data.get('latitude')
    # lon = data.get('longitude')
    
    now = get_nepal_time()
    attendance = Attendance(user_id=current_user.id, check_in=now, heartbeat_last=now)
    db.session.add(attendance)
    db.session.flush() # Get attendance ID
    
    # Create TimeLog entry with GPS data
    db.session.add(TimeLog(
        user_id=current_user.id,
        attendance_id=attendance.id,
        timestamp=now,
        ip_address=request.remote_addr,
        device_type=request.headers.get('User-Agent'),
        action='check-in'
    ))
    
    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id, 
        action=f"Checked in successfully via Dashboard", 
        ip_address=request.remote_addr
    ))
    
    # Trigger Saturday Sync for current week (last 7 days and next 7 days)
    AttendanceService.sync_saturdays_for_period(current_user.id, today - timedelta(days=7), today + timedelta(days=7))
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Checked in successfully.'})

@staff_bp.route('/check-out', methods=['POST'])
@login_required
def check_out():
    today = get_nepal_time().date()
    attendance = Attendance.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Attendance.check_in) == today, 
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        return jsonify({'success': False, 'message': 'No active session.'}), 404

    now = get_nepal_time()
    attendance.check_out = now
    attendance.status = AttendanceService.calculate_status(attendance.check_in, now, role=current_user.role)
    
    # Create TimeLog entry
    db.session.add(TimeLog(
        user_id=current_user.id,
        attendance_id=attendance.id,
        timestamp=now,
        ip_address=request.remote_addr,
        device_type=request.headers.get('User-Agent'),
        action='check-out'
    ))
    
    # Trigger Saturday Sync for current week
    today_dt = get_nepal_time().date()
    AttendanceService.sync_saturdays_for_period(current_user.id, today_dt - timedelta(days=7), today_dt + timedelta(days=7))
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Checked out successfully. Status: {attendance.status}'})

@staff_bp.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    today = get_nepal_time().date()
    attendance = Attendance.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Attendance.check_in) == today, 
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        return jsonify({'success': False, 'message': 'No active session.'}), 404

    now = get_nepal_time()
    attendance.heartbeat_last = now
    attendance.outside_geofence_since = None
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'inside'})
    
@staff_bp.route('/start-break', methods=['POST'])
@login_required
def start_break():
    now = get_nepal_time()
    
    # Restriction 1: Must be after 2:00 PM (14:00) Nepali Time
    if now.hour < 14:
        return jsonify({'success': False, 'message': 'Break can only be taken after 2:00 PM Nepali time.'}), 400

    today = now.date()
    attendance = Attendance.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Attendance.check_in) == today, 
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        return jsonify({'success': False, 'message': 'No active session.'}), 404
        
    # Restriction 2: Once per day
    if attendance.break_start:
        return jsonify({'success': False, 'message': 'You have already taken your break for today.'}), 400
        
    attendance.break_start = now
    db.session.commit()
    return jsonify({'success': True, 'message': 'Break started.'})

@staff_bp.route('/end-break', methods=['POST'])
@login_required
def end_break():
    today = get_nepal_time().date()
    attendance = Attendance.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Attendance.check_in) == today, 
        Attendance.check_out.is_(None)
    ).first()
    
    if not attendance:
        return jsonify({'success': False, 'message': 'No active session.'}), 404
        
    now = get_nepal_time()
    attendance.break_end = now
    db.session.commit()
    return jsonify({'success': True, 'message': 'Break ended.'})

# ─── My Profile ───────────────────────────────────────────────────────────────
@staff_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    profile = current_user.profile
    if request.method == 'POST':
        profile.personal_email = request.form.get('personal_email', profile.personal_email)
        phone_digits = request.form.get('phone_digits', '').strip()
        if phone_digits:
            profile.phone = f"+977 {phone_digits}"
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('staff.my_profile'))
    if current_user.role == 'student':
        return render_template('employee/student_profile.html', profile=profile)
    return render_template('employee/my_profile.html', profile=profile)

# ─── My Queries ───────────────────────────────────────────────────────────────
@staff_bp.route('/queries', methods=['GET', 'POST'])
@login_required
def my_queries():
    from database.models import ContactQuery
    if request.method == 'POST':
        category = request.form.get('category')
        priority = request.form.get('priority')
        message = request.form.get('message')
        query = ContactQuery(
            name=current_user.profile.full_name if current_user.profile else current_user.email,
            email=current_user.email,
            category=category,
            priority=priority,
            message=message
        )
        db.session.add(query)
        db.session.commit()
        flash('Query submitted successfully. Admin will respond soon.', 'success')
        return redirect(url_for('staff.my_queries'))
    queries = ContactQuery.query.filter_by(email=current_user.email).order_by(ContactQuery.created_at.desc()).all()
    return render_template('employee/my_queries.html', queries=queries)

# ─── Leaves ───────────────────────────────────────────────────────────────────
@staff_bp.route('/leaves', methods=['GET', 'POST'])
@login_required
def my_leaves():
    from utils.leave_service import LeaveService
    annual_allowance = current_user.profile.leave_allowance if current_user.profile else 15.0
    leave_balance = LeaveService.calculate_leave_balance(current_user.id, annual_allowance)
    
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        reason = request.form.get('reason')
        from datetime import date
        
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
        
        # Guard: No past leaves
        if start_date < get_nepal_time().date():
            flash('Cannot apply for leave on a past date.', 'error')
            return redirect(url_for('staff.my_leaves'))
            
        # Guard: End date before start date
        if end_date < start_date:
            flash('End date must be after start date.', 'error')
            return redirect(url_for('staff.my_leaves'))
            
        leave = LeaveRequest(
            user_id=current_user.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='pending'
        )
        db.session.add(leave)
        db.session.commit()
        flash('Leave request submitted successfully.', 'success')
        return redirect(url_for('staff.my_leaves'))
        
    leaves = LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.applied_on.desc()).all()
    return render_template('employee/my_leaves.html', leaves=leaves, leave_balance=leave_balance)

# ─── Calendar Events API ──────────────────────────────────────────────────────
@staff_bp.route('/attendance/events')
@login_required
def attendance_events():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    events = []
    
    # 1. Fetch Attendance Records
    query = Attendance.query.filter_by(user_id=current_user.id)
    if start_str and end_str:
        start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
        end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
        query = query.filter(db.func.date(Attendance.check_in) >= start_date, 
                             db.func.date(Attendance.check_in) <= end_date)
                             
    attendances = query.all()
    
    for att in attendances:
        color = '#10b981' # Green (present by default)
        title = att.status.title()
        
        if att.status == 'absent':
            color = '#ef4444' # Red
        elif att.status == 'half-day' or att.status == 'late' or att.status == 'weekend':
            color = '#f59e0b' # Amber
            
        event = {
            'id': f'att_{att.id}',
            'title': title,
            'color': color,
        }
        
        if att.check_out:
            event['start'] = att.check_in.isoformat()
            event['end'] = att.check_out.isoformat()
            event['allDay'] = False
        elif att.status != 'absent' and att.status != 'weekend':
            event['start'] = att.check_in.isoformat()
            event['allDay'] = False
        else: # absent / weekend fallback to all day
            event['start'] = att.check_in.strftime('%Y-%m-%d')
            event['allDay'] = True
            
        events.append(event)
        
    # 2. Fetch Approved Leave Requests
    leave_query = LeaveRequest.query.filter_by(user_id=current_user.id, status='approved')
    if start_str and end_str:
        leave_query = leave_query.filter(
            db.or_(
                db.and_(LeaveRequest.start_date >= start_date, LeaveRequest.start_date <= end_date),
                db.and_(LeaveRequest.end_date >= start_date, LeaveRequest.end_date <= end_date),
                db.and_(LeaveRequest.start_date <= start_date, LeaveRequest.end_date >= end_date)
            )
        )
        
    approved_leaves = leave_query.all()
    
    for leave in approved_leaves:
        # FullCalendar needs end date to be exclusive for range
        end_dt = leave.end_date + timedelta(days=1)
        
        events.append({
            'id': f'leave_{leave.id}',
            'title': f'On Leave ({leave.leave_type.title()})',
            'start': leave.start_date.isoformat(),
            'end': end_dt.isoformat(),
            'color': '#8b5cf6', # Purple
            'allDay': True
        })
        
    return jsonify(events)

# ─── Payslips ─────────────────────────────────────────────────────────────────
@staff_bp.route('/payslips')
@login_required
def my_payslips():
    payslips = Payroll.query.filter_by(user_id=current_user.id).order_by(Payroll.generated_on.desc()).all()
    return render_template('employee/my_payslips.html', payslips=payslips, profile=current_user.profile)

@staff_bp.route('/payslip/<int:payroll_id>')
@login_required
def view_my_payslip(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    if payroll.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('staff.my_payslips'))
        
    from datetime import datetime
    month_str = datetime(payroll.year, payroll.month, 1).strftime('%B %Y')
    return render_template('admin/payslip_template.html', p=payroll, month_str=month_str)
    
if __name__ == '__main__':
    # This allows developers to run this file directly to start the dev server
    import sys
    import os
    # Add parent directory to path so we can import run_dev
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from run_dev import run_dev
    run_dev()

