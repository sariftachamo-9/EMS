from extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
import pytz
from utils.time_utils import get_nepal_time
from utils.encryption_utils import EncryptionService
import os

class EncryptedType(db.TypeDecorator):
    """
    Transparently encrypt and decrypt data as it passes through the ORM.
    """
    impl = db.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return EncryptionService.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return EncryptionService.decrypt(value)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True) # Added for QR badge system
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee') # admin, employee, intern, student
    otp = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    current_session_id = db.Column(db.String(100), nullable=True)
    location_bypass_until = db.Column(db.DateTime, nullable=True) # For 24h admin bypass
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_nepal_time)

    # Relationships
    profile = db.relationship('EmployeeProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    attendances = db.relationship('Attendance', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    leave_requests = db.relationship('LeaveRequest', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    payrolls = db.relationship('Payroll', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    login_tokens = db.relationship('LoginToken', backref='user', lazy='dynamic', cascade="all, delete-orphan")



class LoginLog(db.Model):
    __tablename__ = 'login_logs'
    log_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    user_id = db.Column(db.String(50))
    role = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    login_time = db.Column(db.DateTime, default=get_nepal_time)

class EmployeeProfile(db.Model):
    __tablename__ = 'employee_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(50))
    designation = db.Column(db.String(50))
    joining_date = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Float, default=0.0)
    hra = db.Column(db.Float, default=0.0)
    transport_allowance = db.Column(db.Float, default=0.0)
    other_allowances = db.Column(db.Float, default=0.0)
    bank_account = db.Column(EncryptedType(255))
    pan_number = db.Column(EncryptedType(255))
    personal_email = db.Column(EncryptedType(255))
    phone = db.Column(EncryptedType(255))
    overtime_rate = db.Column(db.Float, default=0.0)
    leave_allowance = db.Column(db.Float, default=15.0)
    tax_deduction = db.Column(db.Float, default=0.0)
    insurance_deduction = db.Column(db.Float, default=0.0)
    other_deductions = db.Column(db.Float, default=0.0)
    workshop_end_date = db.Column(db.Date)
    payment_status = db.Column(db.String(20))
    workshop_status = db.Column(db.String(20), default='Ongoing')

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='present') # present, late, half-day, absent
    overtime_hours = db.Column(db.Float, default=0.0)
    heartbeat_last = db.Column(db.DateTime, nullable=True)
    outside_geofence_since = db.Column(db.DateTime, nullable=True)
    break_start = db.Column(db.DateTime, nullable=True)
    break_end = db.Column(db.DateTime, nullable=True)
    is_weekend = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.Index('idx_attendance_user_checkin', 'user_id', 'check_in'),
    )

class TimeLog(db.Model):
    __tablename__ = 'time_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attendance_id = db.Column(db.Integer, db.ForeignKey('attendance.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_nepal_time)
    ip_address = db.Column(db.String(45))
    device_type = db.Column(db.String(100))
    action = db.Column(db.String(20)) # 'check-in' or 'check-out'

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type = db.Column(db.String(20), nullable=False) # sick, casual, annual
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    applied_on = db.Column(db.DateTime, default=get_nepal_time)

    __table_args__ = (
        db.Index('idx_leave_user_status', 'user_id', 'status'),
    )

class Payroll(db.Model):
    __tablename__ = 'payrolls'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    
    # Snapshotted Data
    snapshot_base_salary = db.Column(db.Float)
    snapshot_hra = db.Column(db.Float)
    snapshot_transport = db.Column(db.Float)
    
    # Calculations
    overtime_earnings = db.Column(db.Float, default=0.0)
    lop_deduction = db.Column(db.Float, default=0.0)
    gross_pay = db.Column(db.Float)
    net_pay = db.Column(db.Float)
    
    payslip_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='generated') # generated, paid
    generated_on = db.Column(db.DateTime, default=get_nepal_time)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=get_nepal_time)

class ContactQuery(db.Model):
    __tablename__ = 'contact_queries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    category = db.Column(db.String(50)) # HR, Technical, Finance, etc.
    priority = db.Column(db.String(10), default='Medium') # Low, Medium, High
    subject = db.Column(db.String(200))
    message = db.Column(db.Text) # legacy field
    description = db.Column(db.Text) # detailed inquiry
    is_anonymous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='open') # open, in-progress, resolved
    created_at = db.Column(db.DateTime, default=get_nepal_time)

    # Relationship
    user_ref = db.relationship('User', backref='queries')

class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)   # Formal message
    is_active = db.Column(db.Boolean, default=True) # Toggle visibility
    role_restriction = db.Column(db.String(20)) # all, admin, employee
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # private notice
    notice_type = db.Column(db.String(100), default='General Announcement Notices')
    created_at = db.Column(db.DateTime, default=get_nepal_time)

class OfficeSettings(db.Model):
    __tablename__ = 'office_settings'
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, default=27.7172)
    longitude = db.Column(db.Float, default=85.3240)
    radius = db.Column(db.Integer, default=100)
    office_ip = db.Column(db.String(45))
    auto_checkout_enabled = db.Column(db.Boolean, default=True)
    auto_checkout_time = db.Column(db.Time, default=datetime.strptime('18:00', '%H:%M').time())  # 6 PM
    email_reminders_enabled = db.Column(db.Boolean, default=True)
    reminder_time_before_checkout = db.Column(db.Integer, default=30)  # minutes before auto-checkout

class AllowedLocation(db.Model):
    __tablename__ = 'allowed_locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    radius = db.Column(db.Integer, default=100) # Radius in meters
    is_active = db.Column(db.Boolean, default=True)

class BlockedIP(db.Model):
    __tablename__ = 'blocked_ips'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    reason = db.Column(db.String(100))
    stage = db.Column(db.Integer, default=0)
    attempts = db.Column(db.Integer, default=1)
    last_attempt_at = db.Column(db.DateTime, default=get_nepal_time)
    blocked_until = db.Column(db.DateTime, nullable=True)

class LoginToken(db.Model):
    __tablename__ = 'login_tokens'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_nepal_time)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    browser_fingerprint = db.Column(db.String(64), nullable=True) # Binding to browser session
    is_viewed = db.Column(db.Boolean, default=False)             # One-time view protection

class VerificationToken(db.Model):
    __tablename__ = 'verification_tokens'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    session_id = db.Column(db.String(100), nullable=True) # Optional link to session
    status = db.Column(db.String(20), default='pending') # pending, verified, rejected
    is_verified = db.Column(db.Boolean, default=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=get_nepal_time)
    expires_at = db.Column(db.DateTime, nullable=False)
