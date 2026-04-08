from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from utils.time_utils import get_nepal_time
import secrets
from datetime import datetime, timedelta
from database.models import User, EmployeeProfile, Attendance, LeaveRequest, Payroll, LoginToken, ContactQuery, AuditLog, OfficeSettings, AllowedLocation, Notice
from utils.id_generator import generate_staff_id
from utils.email_service import send_notice_broadcast
from werkzeug.security import generate_password_hash
from utils.security_utils import validate_password_strength
from utils.excel_sync import ExcelSyncService
import re

admin_bp = Blueprint('admin', __name__)

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied.', 'danger')
            return redirect(url_for('staff.dashboard'))
        return func(*args, **kwargs)
    return wrapper

@admin_bp.route('/generate-qr-login/<int:user_id>')
@login_required
@admin_required
def generate_qr_login(user_id):
    token = secrets.token_hex(16)
    expires = get_nepal_time() + timedelta(minutes=5)
    
    # Invalidate old tokens for this user
    LoginToken.query.filter_by(user_id=user_id, used=False).update({'used': True})
    
    new_token = LoginToken(token=token, user_id=user_id, expires_at=expires)
    db.session.add(new_token)
    db.session.commit()
    
    qr_url = url_for('auth.qr_login', token=token, _external=True)
    return jsonify({'success': True, 'qr_url': qr_url})

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/employees')
@login_required
@admin_required
def employees():
    search = request.args.get('search', '')
    dept = request.args.get('dept', '')
    desig = request.args.get('desig', '')
    
    query = User.query.join(EmployeeProfile).filter(User.role == 'employee')
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%')
        ))
    if dept:
        query = query.filter(EmployeeProfile.department == dept)
    if desig:
        query = query.filter(EmployeeProfile.designation == desig)
        
    users = query.all()
    # Get unique depts and desigs for filters
    depts = db.session.query(EmployeeProfile.department).distinct().filter(EmployeeProfile.department != None).all()
    desigs = db.session.query(EmployeeProfile.designation).distinct().filter(EmployeeProfile.designation != None).all()
    
    return render_template('admin/staff_directory.html', 
                           users=users, 
                           title="Employees List", 
                           admin_title="Employee Management",
                           add_label="Add Employee",
                           add_endpoint="admin.add_employee",
                           depts=[d[0] for d in depts],
                           desigs=[d[0] for d in desigs],
                           curr_dept=dept,
                           curr_desig=desig,
                           curr_search=search,
                           now=get_nepal_time())

@admin_bp.route('/interns')
@login_required
@admin_required
def interns():
    search = request.args.get('search', '')
    dept = request.args.get('dept', '')
    desig = request.args.get('desig', '')
    
    query = User.query.join(EmployeeProfile).filter(User.role == 'intern')
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%')
        ))
    if dept:
        query = query.filter(EmployeeProfile.department == dept)
    if desig:
        query = query.filter(EmployeeProfile.designation == desig)
        
    users = query.all()
    
    # Get unique depts and desigs for filters
    depts = db.session.query(EmployeeProfile.department).distinct().filter(EmployeeProfile.department != None).all()
    desigs = db.session.query(EmployeeProfile.designation).distinct().filter(EmployeeProfile.designation != None).all()
    
    return render_template('admin/staff_directory.html', 
                           users=users, 
                           title="Interns List", 
                           admin_title="Intern Management",
                           add_label="Add Intern",
                           add_endpoint="admin.add_intern",
                           depts=[d[0] for d in depts],
                           desigs=[d[0] for d in desigs],
                           curr_dept=dept,
                           curr_desig=desig,
                           curr_search=search,
                           now=get_nepal_time())

@admin_bp.route('/students')
@login_required
@admin_required
def students():
    search = request.args.get('search', '')
    dept = request.args.get('dept', '')
    desig = request.args.get('desig', '')
    
    query = User.query.join(EmployeeProfile).filter(User.role == 'student')
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%')
        ))
    if dept:
        query = query.filter(EmployeeProfile.department == dept)
    if desig:
        query = query.filter(EmployeeProfile.designation == desig)
        
    users = query.all()
    
    # Get unique depts and desigs for filters
    depts = db.session.query(EmployeeProfile.department).distinct().filter(EmployeeProfile.department != None).all()
    desigs = db.session.query(EmployeeProfile.designation).distinct().filter(EmployeeProfile.designation != None).all()
    
    return render_template('admin/staff_directory.html', 
                           users=users, 
                           title="Students List", 
                           admin_title="Student Management",
                           add_label="Add Student",
                           add_endpoint="admin.add_student",
                           depts=[d[0] for d in depts],
                           desigs=[d[0] for d in desigs],
                           curr_dept=dept,
                           curr_desig=desig,
                           curr_search=search,
                           now=get_nepal_time())

@admin_bp.route('/employee-queries')
@login_required
@admin_required
def employee_queries():
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    
    query = ContactQuery.query
    
    if search:
        query = query.filter(db.or_(
            ContactQuery.name.ilike(f'%{search}%'),
            ContactQuery.email.ilike(f'%{search}%'),
            ContactQuery.message.ilike(f'%{search}%')
        ))
    if status:
        query = query.filter(ContactQuery.status == status)
    if priority:
        query = query.filter(ContactQuery.priority == priority)
        
    queries = query.order_by(ContactQuery.created_at.desc()).all()
    return render_template('admin/queries.html', queries=queries)

@admin_bp.route('/query/update/<int:query_id>', methods=['POST'])
@login_required
@admin_required
def update_query(query_id):
    query = ContactQuery.query.get_or_404(query_id)
    query.status = request.form.get('status')
    query.priority = request.form.get('priority')
    db.session.commit()
    flash('Query updated.', 'success')
    return redirect(url_for('admin.employee_queries'))

@admin_bp.route('/leave-requests')
@login_required
@admin_required
def leave_requests():
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    leave_type = request.args.get('leave_type', '')
    
    query = LeaveRequest.query.join(User).join(EmployeeProfile)
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%')
        ))
    if status:
        query = query.filter(LeaveRequest.status == status)
    if leave_type:
        query = query.filter(LeaveRequest.leave_type == leave_type)
        
    requests = query.order_by(LeaveRequest.applied_on.desc()).all()
    
    return render_template('admin/leaves.html', 
                           requests=requests,
                           curr_search=search,
                           curr_status=status,
                           curr_leave_type=leave_type)

@admin_bp.route('/approve-leave/<int:leave_id>/<string:status>', methods=['POST'])
@login_required
@admin_required
def approve_leave(leave_id, status):
    req = LeaveRequest.query.get_or_404(leave_id)
    if status in ['approved', 'rejected']:
        req.status = status
        db.session.commit()
        flash(f'Leave request {status}.', 'success')
    return redirect(url_for('admin.leave_requests'))

@admin_bp.route('/attendance')
@login_required
@admin_required
def attendance():
    search = request.args.get('search', '')
    date_str = request.args.get('date', '')
    dept = request.args.get('dept', '')
    status = request.args.get('status', '') # present, late, absent, on_leave
    user_id = request.args.get('user_id')
    
    today = get_nepal_time().date()
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today
    
    # Base query for existing attendance records
    query = Attendance.query.join(User).join(EmployeeProfile)
    
    # Filter by date using an index-friendly range (Start of Day to End of Day)
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    query = query.filter(
        Attendance.check_in >= start_of_day,
        Attendance.check_in <= end_of_day
    )
    
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%')
        ))
    if dept:
        query = query.filter(EmployeeProfile.department == dept)
    if status and status != 'on_leave':
        query = query.filter(Attendance.status == status)
        
    records = query.order_by(Attendance.check_in.desc()).all()
    
    # Logic for Virtual Records (On Leave)
    virtual_records = []
    if not status or status == 'on_leave':
        # Find approved leave requests that cover target_date
        leaves = LeaveRequest.query.filter(
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date
        ).all()
        
        # Filter leaves by dept/search if needed
        for leave in leaves:
            user = leave.user
            profile = user.profile
            if not profile: continue
            
            # Match search/dept
            matches_search = not search or search.lower() in profile.full_name.lower() or search.lower() in profile.employee_id.lower()
            matches_dept = not dept or profile.department == dept
            
            if matches_search and matches_dept:
                # Only if they DON'T have a real attendance record for this day
                has_record = any(r.user_id == user.id for r in records)
                if not has_record:
                    virtual_records.append({
                        'user': user,
                        'is_virtual': True,
                        'status': 'ON LEAVE',
                        'leave_type': leave.leave_type
                    })

    # If status is strictly 'on_leave', only show virtuals
    if status == 'on_leave':
        display_records = virtual_records
    else:
        display_records = records + virtual_records

    # Filter metadata for template
    depts = db.session.query(EmployeeProfile.department).distinct().filter(EmployeeProfile.department != None).all()

    return render_template('admin/attendance.html', 
                           records=display_records,
                           depts=[d[0] for d in depts],
                           curr_date=target_date.strftime('%Y-%m-%d'),
                           curr_dept=dept,
                           curr_status=status,
                           curr_search=search)

@admin_bp.route('/notices', methods=['GET', 'POST'])
@login_required
@admin_required
def notices():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        role = request.form.get('role', 'all')
        notice_type = request.form.get('notice_type', 'General Announcement Notices')
        
        notice = Notice(title=title, content=content, role_restriction=role, notice_type=notice_type, is_active=True)
        db.session.add(notice)
        
        # Audit Log
        log = AuditLog(
            user_id=current_user.id,
            action=f"Created Notice: {title} (Target: {role.capitalize()})",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        # Background Broadcast
        if role == 'all':
            target_users = User.query.filter(User.role != 'admin').all()
        else:
            target_users = User.query.filter_by(role=role).all()
        
        emails = [u.profile.personal_email or u.email for u in target_users if u.profile]
        if emails:
            send_notice_broadcast(emails, title, content)
            
        flash('Notice broadcasted successfully and emailed to staff.', 'success')
        return redirect(url_for('admin.notices'))
        
    notices_query = Notice.query
    search = request.args.get('search', '')
    filter_date = request.args.get('date', '')
    
    if search:
        notices_query = notices_query.filter(db.or_(
            Notice.title.ilike(f'%{search}%'),
            Notice.content.ilike(f'%{search}%')
        ))
        
    if filter_date:
        from sqlalchemy import cast, Date
        notices_query = notices_query.filter(cast(Notice.created_at, Date) == filter_date)
        
    notices = notices_query.order_by(Notice.created_at.desc()).all()
    return render_template('admin/notices.html', notices=notices, curr_search=search, curr_date=filter_date)

@admin_bp.route('/notices/delete/<int:notice_id>', methods=['POST'])
@login_required
@admin_required
def delete_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    title = notice.title
    db.session.delete(notice)
    
    # Audit Log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Deleted Notice: {title}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    flash('Notice deleted successfully.', 'success')
    return redirect(url_for('admin.notices'))

@admin_bp.route('/payroll')
@login_required
@admin_required
def payroll():
    from collections import defaultdict
    user_id = request.args.get('user_id')
    
    # If a specific user is requested, we can show their history or highlight them
    # For now, we'll just allow the template to filter if needed, 
    # but let's add logic to fetch a specific user's payroll if user_id is provided.
    
    today = get_nepal_time().date()
    current_year = today.year
    current_month = today.month

    # 1. Salary Expenditure Trend (Last 6 Months)
    trend_labels = []
    trend_data = []
    # Generate last 6 months list starting from current month backwards
    for i in range(5, -1, -1):
        # Use proper month arithmetic to avoid timedelta edge cases
        m = current_month - i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
            
        trend_labels.append(f"{y}-{m:02d}")
        
        total_salary = db.session.query(db.func.sum(Payroll.net_pay)).filter(
            Payroll.year == y,
            Payroll.month == m
        ).scalar() or 0.0
        
        trend_data.append(float(total_salary))

    # 2. Department-Wise Breakdown (Latest)
    dept_query = db.session.query(
        EmployeeProfile.department,
        db.func.count(EmployeeProfile.id)
    ).join(User).filter(User.role == 'employee', User.is_active == True).group_by(EmployeeProfile.department).all()
    
    dept_labels = [d[0] for d in dept_query]
    dept_data = [d[1] for d in dept_query]

    # 3. Payroll History (Grouped by Month/Year)
    history_query = db.session.query(
        Payroll.year,
        Payroll.month,
        db.func.count(Payroll.id).label('employees'),
        db.func.sum(Payroll.net_pay).label('total_salary'),
        db.func.max(Payroll.status).label('status') # Assuming status is relatively uniform per batch
    ).group_by(Payroll.year, Payroll.month).order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    
    history_data = []
    for r in history_query:
        history_data.append({
            'month_str': f"{r.year}-{r.month:02d}",
            'year': r.year,
            'month': r.month,
            'employees': r.employees,
            'total_salary': float(r.total_salary or 0),
            'status': r.status.capitalize() if r.status else 'Generated'
        })
        
    return render_template('admin/payroll.html', 
                           trend_labels=trend_labels, 
                           trend_data=trend_data,
                           dept_labels=dept_labels,
                           dept_data=dept_data,
                           history_data=history_data)

@admin_bp.route('/payroll/batch/<int:year>/<int:month>')
@login_required
@admin_required
def payroll_batch(year, month):
    search = request.args.get('search', '')
    query = Payroll.query.join(User).join(EmployeeProfile).filter(Payroll.year == year, Payroll.month == month)
    
    if search:
        query = query.filter(db.or_(
            EmployeeProfile.full_name.ilike(f'%{search}%'),
            EmployeeProfile.employee_id.ilike(f'%{search}%')
        ))
        
    payrolls = query.all()
    from datetime import datetime
    month_str = datetime(year, month, 1).strftime('%B %Y')
    return render_template('admin/payroll_batch.html', payrolls=payrolls, month_str=month_str, curr_search=search)

@admin_bp.route('/payroll/payslip/<int:payroll_id>')
@login_required
@admin_required
def view_payslip(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    from datetime import datetime
    month_str = datetime(payroll.year, payroll.month, 1).strftime('%B %Y')
    return render_template('admin/payslip_template.html', p=payroll, month_str=month_str)

@admin_bp.route('/payroll/generate', methods=['POST'])
@login_required
@admin_required
def generate_payroll():
    month_str = request.form.get('month')
    if not month_str:
        flash('Please select a month.', 'danger')
        return redirect(url_for('admin.payroll'))
        
    try:
        year, month = map(int, month_str.split('-'))
    except ValueError:
        flash('Invalid month format.', 'danger')
        return redirect(url_for('admin.payroll'))
        
    # We no longer block if the batch exists. Instead, we update unpaid records.
    from utils.payroll_service import PayrollService
    users = User.query.filter(User.role != 'admin', User.is_active == True).all()
    
    generated: int = 0
    updated: int = 0
    skipped: int = 0
    
    for user in users:
        if not user.profile:
            continue
            
        # Calculate salary based on attendance
        salary_data = PayrollService.calculate_monthly_salary(user.id, month, year)
        if not salary_data:
            continue
            
        pr = Payroll.query.filter_by(user_id=user.id, month=month, year=year).first()
        
        if pr:
            if pr.status == 'paid':
                skipped += 1
                continue
            
            # Update existing un-paid record
            pr.lop_deduction = salary_data['deductions']
            pr.gross_pay = salary_data['gross_pay']
            pr.net_pay = salary_data['net_pay']
            pr.snapshot_base_salary = user.profile.base_salary
            pr.snapshot_hra = user.profile.hra
            pr.snapshot_transport = user.profile.transport_allowance
            updated += 1
        else:
            # Create new record
            pr = Payroll(
                user_id=user.id,
                month=month,
                year=year,
                snapshot_base_salary=user.profile.base_salary,
                snapshot_hra=user.profile.hra,
                snapshot_transport=user.profile.transport_allowance,
                overtime_earnings=0.0,
                lop_deduction=salary_data['deductions'],
                gross_pay=salary_data['gross_pay'],
                net_pay=salary_data['net_pay'],
                status='generated'
            )
            db.session.add(pr)
            generated += 1
        
    db.session.commit()
    
    total_processed = generated + updated
    if total_processed > 0:
        db.session.add(AuditLog(user_id=current_user.id, action=f"Generated/Updated Payroll batch for {month_str}", ip_address=request.remote_addr))
        db.session.commit()
        
        msg = f'Success! Generated {generated} new records and updated {updated} existing records for {month_str}.'
        if skipped > 0:
            msg += f' (Skipped {skipped} already paid).'
        flash(msg, 'success')
    else:
        flash('No active employees found to generate payroll.', 'info')
        
    return redirect(url_for('admin.payroll'))




@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('admin/audit_logs.html', logs=logs)

@admin_bp.route('/office-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def office_settings():
    settings = OfficeSettings.query.first()
    if request.method == 'POST':
        if not settings:
            settings = OfficeSettings()
            db.session.add(settings)
        
        try:
            lat = request.form.get('latitude')
            lng = request.form.get('longitude')
            rad = request.form.get('radius')
            
            if lat: settings.latitude = float(lat)
            if lng: settings.longitude = float(lng)
            if rad: settings.radius = int(rad)
            settings.office_ip = request.form.get('office_ip', '')
            
            # Create AuditLog for updating settings
            log = AuditLog(
                user_id=current_user.id,
                action="Updated Primary Office Settings",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            
            db.session.commit()
            flash('Office settings updated.', 'success')
        except ValueError:
            flash('Invalid input for latitude, longitude, or radius.', 'danger')
            
        return redirect(url_for('admin.office_settings'))
        
    allowed_locations = AllowedLocation.query.all()
    return render_template('admin/settings.html', settings=settings, allowed_locations=allowed_locations)

@admin_bp.route('/allowed-locations/add', methods=['POST'])
@login_required
@admin_required
def add_allowed_location():
    name = request.form.get('name', '').strip()
    lat = request.form.get('latitude', '').strip()
    lng = request.form.get('longitude', '').strip()
    radius = request.form.get('radius', '100').strip()

    if not name or not lat or not lng:
        flash('Name, latitude, and longitude are required for a secondary location.', 'danger')
        return redirect(url_for('admin.office_settings'))

    try:
        loc = AllowedLocation(
            name=name,
            latitude=float(lat),
            longitude=float(lng),
            radius=int(radius),
            is_active=True
        )
        db.session.add(loc)
        db.session.add(AuditLog(
            user_id=current_user.id,
            action=f"Added secondary office location: {name}",
            ip_address=request.remote_addr
        ))
        db.session.commit()
        flash(f'Secondary location "{name}" added successfully.', 'success')
    except ValueError:
        flash('Invalid coordinates or radius value.', 'danger')

    return redirect(url_for('admin.office_settings'))


@admin_bp.route('/allowed-locations/delete/<int:loc_id>', methods=['POST'])
@login_required
@admin_required
def delete_allowed_location(loc_id):
    loc = AllowedLocation.query.get_or_404(loc_id)
    name = loc.name
    db.session.delete(loc)
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Deleted secondary office location: {name}",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    flash(f'Location "{name}" removed.', 'info')
    return redirect(url_for('admin.office_settings'))


@admin_bp.route('/allowed-locations/toggle/<int:loc_id>', methods=['POST'])
@login_required
@admin_required
def toggle_allowed_location(loc_id):
    loc = AllowedLocation.query.get_or_404(loc_id)
    loc.is_active = not loc.is_active
    db.session.commit()
    status = 'enabled' if loc.is_active else 'disabled'
    flash(f'Location "{loc.name}" {status}.', 'success')
    return redirect(url_for('admin.office_settings'))


@admin_bp.route('/add-employee', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        return _internal_onboard_logic(request, role='employee', target='admin.employees')
    return render_template('admin/add_employee.html')

@admin_bp.route('/add-intern', methods=['GET', 'POST'])
@login_required
@admin_required
def add_intern():
    if request.method == 'POST':
        return _internal_onboard_logic(request, role='intern', target='admin.interns')
    return render_template('admin/add_intern.html')

@admin_bp.route('/add-student', methods=['GET', 'POST'])
@login_required
@admin_required
def add_student():
    if request.method == 'POST':
        return _internal_onboard_logic(request, role='student', target='admin.students')
    return render_template('admin/add_student.html')

def _internal_onboard_logic(request, role, target):
    login_email = request.form.get('login_email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    middle_name = request.form.get('middle_name', '').strip()
    last_name = request.form.get('last_name')
    personal_email = request.form.get('personal_email')
    department = request.form.get('department')
    designation = request.form.get('designation')
    phone_digits = request.form.get('phone_digits')
    phone = f"+977 {phone_digits}"
    salary = float(request.form.get('salary', 0))
    ot_rate = float(request.form.get('ot_rate', 0))
    leave_days = float(request.form.get('leave_days', 15.0))
    
    # Workshop fields for students
    workshop_end_date = None
    payment_status = None
    hra_amount = float(request.form.get('hra', 0)) # Used as Paid Amount for students
    
    if role == 'student':
        joining_date_str = request.form.get('workshop_start_date')
        workshop_end_date_str = request.form.get('workshop_end_date')
        if joining_date_str:
            joining_date = datetime.strptime(joining_date_str, '%Y-%m-%d').date()
        else:
            joining_date = get_nepal_time().date()
            
        if workshop_end_date_str:
            workshop_end_date = datetime.strptime(workshop_end_date_str, '%Y-%m-%d').date()
            
        payment_status = request.form.get('payment_status', 'Unpaid')
        workshop_status = request.form.get('workshop_status', 'Ongoing')
    else:
        joining_date = get_nepal_time().date()
        workshop_status = 'N/A' # Not applicable for employees/interns
    
    # Validation
    if not login_email.endswith('@ems.com'):
        flash('Login email must end with @ems.com', 'danger')
        return redirect(url_for(f'admin.add_{role}'))
        
    phone_pattern = re.compile(r'^\+977\s?(98|97|96)\d{8}$')
    if not phone_pattern.match(phone):
        flash('Invalid phone format. Must be +977 followed by 98/97/96 and 8 digits.', 'danger')
        return redirect(url_for(f'admin.add_{role}'))
        
    if User.query.filter_by(email=login_email).first():
        flash('User already exists with this login email.', 'danger')
        return redirect(url_for(f'admin.add_{role}'))

    # Security: Backend Password Strength Validation
    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        flash(msg, 'danger')
        return redirect(url_for(f'admin.add_{role}'))

    # 1. Create User
    new_user = User(
        email=login_email,
        password_hash=generate_password_hash(password),
        role=role
    )
    db.session.add(new_user)
    db.session.flush() # Get user ID
    
    # 2. Generate Staff ID
    staff_id = generate_staff_id(role, department)
    
    # 3. Create Profile
    full_name = f"{first_name} {middle_name} {last_name}" if middle_name else f"{first_name} {last_name}"
    
    new_profile = EmployeeProfile(
        user_id=new_user.id,
        full_name=full_name,
        employee_id=staff_id,
        department=department,
        designation=designation,
        joining_date=joining_date,
        base_salary=salary,
        hra=hra_amount,
        personal_email=personal_email,
        phone=phone,
        overtime_rate=ot_rate,
        leave_allowance=leave_days,
        workshop_end_date=workshop_end_date,
        payment_status=payment_status,
        workshop_status=workshop_status
    )
    db.session.add(new_profile)
    db.session.commit()
    
    # Sync to Excel
    ExcelSyncService.sync_role_to_excel(role)
    
    flash(f'Staff created successfully! ID: {staff_id}', 'success')
    return redirect(url_for(target))

@admin_bp.route('/staff/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_staff(user_id):
    user = User.query.get_or_404(user_id)
    profile = user.profile
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name', '').strip()
        last_name = request.form.get('last_name')
        personal_email = request.form.get('personal_email')
        department = request.form.get('department')
        designation = request.form.get('designation')
        phone_digits = request.form.get('phone_digits')
        phone = f"+977 {phone_digits}"
        salary = float(request.form.get('salary', 0))
        ot_rate = float(request.form.get('ot_rate', 0))
        leave_days = float(request.form.get('leave_days', 15.0))
        role = request.form.get('role', 'employee')
        
        # Student specific fields
        hra_amount = float(request.form.get('hra', 0))
        if role == 'student':
            joining_date_str = request.form.get('workshop_start_date')
            workshop_end_date_str = request.form.get('workshop_end_date')
            if joining_date_str:
                profile.joining_date = datetime.strptime(joining_date_str, '%Y-%m-%d').date()
            if workshop_end_date_str:
                profile.workshop_end_date = datetime.strptime(workshop_end_date_str, '%Y-%m-%d').date()
            profile.payment_status = request.form.get('payment_status', 'Unpaid')
            profile.workshop_status = request.form.get('workshop_status', 'Ongoing')
        
        # We don't allow changing login email easily here for security/complexity
        # but we update the profile and user role
        user.role = role
        
        profile.full_name = f"{first_name} {middle_name} {last_name}" if middle_name else f"{first_name} {last_name}"
        profile.personal_email = personal_email
        profile.department = department
        profile.designation = designation
        profile.phone = phone
        profile.base_salary = salary
        profile.hra = hra_amount
        profile.overtime_rate = ot_rate
        profile.leave_allowance = leave_days
        
        db.session.commit()
        
        # Enhanced Audit Logging
        db.session.add(AuditLog(
            user_id=current_user.id,
            action=f"Updated Staff Profile: {profile.full_name} ({profile.employee_id})",
            details=f"Edited by {current_user.email}. Fields updated: Name, Dept, Desig, Salary, etc.",
            ip_address=request.remote_addr
        ))
        db.session.commit()
        
        # Sync to Excel
        ExcelSyncService.sync_role_to_excel(role)
        
        flash('Staff profile updated successfully.', 'success')
        
        if role == 'employee':
            target = 'admin.employees'
        elif role == 'intern':
            target = 'admin.interns'
        else:
            target = 'admin.students'
        return redirect(url_for(target))
        
    return render_template('admin/edit_staff.html', user=user, profile=profile)

@admin_bp.route('/staff/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_staff(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot delete admin user.', 'danger')
        return redirect(url_for('admin.employees'))
        
    role = user.role
    db.session.delete(user) # Cascade delete will handle profile
    
    # Enhanced Audit Logging
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Deleted User: {user.email} (Role: {role})",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    # Sync to Excel
    ExcelSyncService.sync_role_to_excel(role)
    
    flash('Staff member deleted successfully.', 'success')
    
    if role == 'employee':
        target = 'admin.employees'
    elif role == 'intern':
        target = 'admin.interns'
    else:
        target = 'admin.students'
    return redirect(url_for(target))

@admin_bp.route('/staff/complete/<int:user_id>')
@login_required
@admin_required
def complete_role(user_id):
    user = User.query.get_or_404(user_id)
    profile = user.profile
    
    if user.role not in ['student', 'intern']:
        flash('Only students or interns can be marked as completed.', 'warning')
        return redirect(url_for('admin.employees'))
        
    if user.role == 'student':
        remaining = (profile.base_salary or 0) - (profile.hra or 0)
        if remaining > 0:
            flash(f'Cannot complete workshop. Student has a remaining balance of Rs.{remaining:,.2f}', 'danger')
            return redirect(url_for('admin.students'))
        msg = f'Workshop marked as completed for {profile.full_name}. Student account is now inactive.'
    else:
        # For interns, we just complete without balance check
        msg = f'Internship marked as completed for {profile.full_name}. Intern account is now inactive.'
        
    profile.workshop_status = 'Completed'
    user.is_active = False # Disable account after completion
    
    # Enhanced Audit Logging
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Marked Role Completed: {profile.full_name} ({user.role})",
        details=f"Account deactivated for {profile.full_name}.",
        ip_address=request.remote_addr
    ))
    db.session.commit()
    
    # Sync to Excel
    ExcelSyncService.sync_role_to_excel(user.role)
    
    flash(msg, 'success')
    target = 'admin.students' if user.role == 'student' else 'admin.interns'
    return redirect(url_for(target))

@admin_bp.route('/api/stats')
@login_required
@admin_required
def get_stats():
    now = get_nepal_time()
    today = now.date()

    # ── 1. Head Counts ─────────────────────────────────────────────────────────
    total_employees = User.query.filter_by(role='employee', is_active=True).count()
    total_interns   = User.query.filter_by(role='intern',   is_active=True).count()
    total_students  = User.query.filter_by(role='student',  is_active=True).count()
    total_active    = total_employees + total_interns + total_students

    # ── 1b. All-time totals (active + inactive) ────────────────────────────────
    all_employees   = User.query.filter_by(role='employee').count()
    all_interns     = User.query.filter_by(role='intern').count()
    all_students    = User.query.filter_by(role='student').count()

    # ── 2. Attendance Today ────────────────────────────────────────────────────
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day   = datetime.combine(today, datetime.max.time())

    attendance_today = db.session.query(Attendance.user_id).filter(
        Attendance.check_in >= start_of_day,
        Attendance.check_in <= end_of_day
    ).distinct().count()

    # Absent today = active staff who have NOT checked in
    absent_today = max(0, (total_employees + total_interns) - attendance_today)
    attendance_rate = round((attendance_today / (total_employees + total_interns) * 100), 1) if (total_employees + total_interns) > 0 else 0.0

    # ── 3. Leaves ──────────────────────────────────────────────────────────────
    pending_leaves  = LeaveRequest.query.filter_by(status='pending').count()
    approved_leaves = LeaveRequest.query.filter_by(status='approved').count()
    rejected_leaves = LeaveRequest.query.filter_by(status='rejected').count()
    total_decided   = approved_leaves + rejected_leaves
    leave_approval_rate = round((approved_leaves / total_decided * 100), 1) if total_decided > 0 else 0.0

    # ── 4. Open Queries ────────────────────────────────────────────────────────
    open_queries = ContactQuery.query.filter(
        db.or_(ContactQuery.status == 'open', ContactQuery.status == 'pending', ContactQuery.status == None)
    ).count()

    # ── 5. New Joinings This Month ─────────────────────────────────────────────
    new_joinings = db.session.query(EmployeeProfile.id).join(User).filter(
        db.extract('month', EmployeeProfile.joining_date) == today.month,
        db.extract('year',  EmployeeProfile.joining_date) == today.year,
        User.is_active == True
    ).count()

    # ── 6. Completed Interns & Students (workshop_status = 'Completed') ────────────
    completed_interns = db.session.query(EmployeeProfile.id).join(User).filter(
        User.role == 'intern',
        EmployeeProfile.workshop_status == 'Completed'
    ).count()

    completed_students = db.session.query(EmployeeProfile.id).join(User).filter(
        User.role == 'student',
        EmployeeProfile.workshop_status == 'Completed'
    ).count()

    # ── 7. Department Distribution (Doughnut) ──────────────────────────────────
    dept_query = db.session.query(
        EmployeeProfile.department,
        db.func.count(EmployeeProfile.id)
    ).join(User).filter(User.is_active == True).group_by(EmployeeProfile.department).all()

    dept_labels = [d[0] for d in dept_query if d[0]]
    dept_values = [d[1] for d in dept_query if d[0]]

    # ── 8. Monthly Leave Trends (Bar – last 6 months) ─────────────────────────
    leave_trends  = []
    trend_labels  = []
    for i in range(5, -1, -1):
        target_month = now.month - i
        target_year  = now.year
        while target_month <= 0:
            target_month += 12
            target_year  -= 1
        month_name = datetime(target_year, target_month, 1).strftime('%b')
        count = LeaveRequest.query.filter(
            db.extract('month', LeaveRequest.applied_on) == target_month,
            db.extract('year',  LeaveRequest.applied_on) == target_year,
            LeaveRequest.status == 'approved'
        ).count()
        trend_labels.append(month_name)
        leave_trends.append(count)

    # ── 9. Recent Activity Feed (last 6 audit logs) ───────────────────────────
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(6).all()
    recent_activity = []
    for log in recent_logs:
        actor = User.query.get(log.user_id)
        actor_name = (actor.profile.full_name.split()[0] if actor and actor.profile and actor.profile.full_name else (actor.email.split('@')[0] if actor else 'System'))
        recent_activity.append({
            'action':  log.action,
            'actor':   actor_name,
            'time':    log.timestamp.strftime('%d %b, %H:%M') if log.timestamp else '—',
            'ip':      log.ip_address or '—'
        })

    # ── 10. Upcoming Approved Leaves (next 7 days) ────────────────────────────
    next_week = today + timedelta(days=7)
    upcoming_leaves_q = LeaveRequest.query.join(User).join(EmployeeProfile).filter(
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date >= today,
        LeaveRequest.start_date <= next_week
    ).order_by(LeaveRequest.start_date.asc()).limit(6).all()

    upcoming_leaves = []
    for lr in upcoming_leaves_q:
        profile = lr.user.profile
        upcoming_leaves.append({
            'name':       profile.full_name if profile else lr.user.email,
            'dept':       profile.department if profile else '—',
            'leave_type': lr.leave_type.title() if lr.leave_type else '—',
            'start':      lr.start_date.strftime('%d %b'),
            'end':        lr.end_date.strftime('%d %b'),
        })

    return jsonify({
        # Head counts (active)
        'total_employees':      total_employees,
        'total_interns':        total_interns,
        'total_students':       total_students,
        'total_active':         total_active,
        # Head counts (all-time totals)
        'all_employees':        all_employees,
        'all_interns':          all_interns,
        'all_students':         all_students,
        # Completed
        'completed_interns':    completed_interns,
        'completed_students':   completed_students,
        # Attendance
        'attendance_today':     attendance_today,
        'absent_today':         absent_today,
        'attendance_rate':      attendance_rate,
        # Leaves
        'pending_leaves':       pending_leaves,
        'leave_approval_rate':  leave_approval_rate,
        # Operations
        'open_queries':         open_queries,
        'new_joinings':         new_joinings,
        # Charts
        'dept_labels':          dept_labels,
        'dept_values':          dept_values,
        'trend_labels':         trend_labels,
        'leave_trends':         leave_trends,
        # Feeds
        'recent_activity':      recent_activity,
        'upcoming_leaves':      upcoming_leaves,
    })

# ─── Staff Detail Views (New) ────────────────────────────────────────────────
@admin_bp.route('/staff/attendance/<int:user_id>')
@login_required
@admin_required
def staff_attendance_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/staff_attendance_detail.html', user=user)

@admin_bp.route('/staff/payroll/<int:user_id>')
@login_required
@admin_required
def staff_payroll_detail(user_id):
    user = User.query.get_or_404(user_id)
    payrolls = Payroll.query.filter_by(user_id=user_id).order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    return render_template('admin/staff_payroll_detail.html', user=user, payrolls=payrolls)

@admin_bp.route('/api/staff/attendance-events/<int:user_id>')
@login_required
@admin_required
def staff_attendance_events(user_id):
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    events = []
    
    # 1. Fetch Attendance Records
    query = Attendance.query.filter_by(user_id=user_id)
    start_date = None
    end_date = None
    if start_str and end_str:
        try:
            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
            query = query.filter(db.func.date(Attendance.check_in) >= start_date, 
                                 db.func.date(Attendance.check_in) <= end_date)
        except (ValueError, TypeError):
            pass
                             
    attendances = query.all()
    
    for att in attendances:
        color = '#10b981' # Green (present by default)
        title = att.status.title()
        
        if att.status == 'absent':
            color = '#ef4444' # Red
        elif att.status in ['half-day', 'late', 'weekend']:
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
        elif att.status not in ['absent', 'weekend']:
            event['start'] = att.check_in.isoformat()
            event['allDay'] = False
        else: # absent / weekend fallback to all day
            event['start'] = att.check_in.strftime('%Y-%m-%d')
            event['allDay'] = True
            
        events.append(event)
        
    # 2. Fetch Approved Leave Requests
    leave_query = LeaveRequest.query.filter_by(user_id=user_id, status='approved')
    if start_str and end_str and start_date and end_date:
        try:
            leave_query = leave_query.filter(
                db.or_(
                    db.and_(LeaveRequest.start_date >= start_date, LeaveRequest.start_date <= end_date),
                    db.and_(LeaveRequest.end_date >= start_date, LeaveRequest.end_date <= end_date)
                )
            )
        except (ValueError, TypeError):
            pass
        
    approved_leaves = leave_query.all()
    for leave in approved_leaves:
        events.append({
            'id': f'leave_{leave.id}',
            'title': f'On Leave ({leave.leave_type.title()})',
            'start': leave.start_date.isoformat(),
            'end': (leave.end_date + timedelta(days=1)).isoformat(),
            'color': '#8b5cf6', # Purple
            'allDay': True
        })
        
    return jsonify(events)


@admin_bp.route('/staff/reactivate/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reactivate_staff(user_id):
    """Reactivate a previously deactivated student or intern account."""
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot modify admin accounts.', 'danger')
        return redirect(url_for('admin.employees'))

    profile = user.profile
    user.is_active = True
    if profile and profile.workshop_status == 'Completed':
        profile.workshop_status = 'Ongoing'

    db.session.add(AuditLog(
        user_id=current_user.id,
        action=f"Reactivated Account: {profile.full_name if profile else user.email} (Role: {user.role})",
        details=f"Account manually reactivated by {current_user.email}.",
        ip_address=request.remote_addr
    ))
    db.session.commit()

    ExcelSyncService.sync_role_to_excel(user.role)

    flash(f'Account for {profile.full_name if profile else user.email} has been reactivated.', 'success')
    target = 'admin.students' if user.role == 'student' else ('admin.interns' if user.role == 'intern' else 'admin.employees')
    return redirect(url_for(target))


