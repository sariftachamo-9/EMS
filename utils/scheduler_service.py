from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
from extensions import db
from database.models import Attendance, User, OfficeSettings, LeaveRequest, AuditLog
from utils.attendance_service import AttendanceService
from utils.email_service import send_email
from utils.time_utils import get_nepal_time
from datetime import datetime, time, timedelta
import pytz

class SchedulerService:
    def __init__(self, app=None):
        self.scheduler = BackgroundScheduler()
        self.app = app

    def init_app(self, app):
        self.app = app
        with app.app_context():
            self._setup_jobs()
        # Don't start automatically to avoid context issues

    def _setup_jobs(self):
        """Setup scheduled jobs based on office settings"""
        # Clear existing jobs
        self.scheduler.remove_all_jobs()

        try:
            # Get office settings
            settings = OfficeSettings.query.first()
            if not settings:
                # Create default settings if none exist
                settings = OfficeSettings()
                db.session.add(settings)
                db.session.commit()
        except Exception as e:
            # If there's a database error (e.g., columns don't exist yet), use defaults
            current_app.logger.warning(f"Could not load office settings for scheduler: {e}. Using defaults.")
            # Create a mock settings object with defaults
            from types import SimpleNamespace
            settings = SimpleNamespace()
            settings.auto_checkout_enabled = True
            settings.auto_checkout_time = datetime.strptime('18:00', '%H:%M').time()
            settings.email_reminders_enabled = True
            settings.reminder_time_before_checkout = 30

        # Schedule Daily Leave Cleanup at 12:05 AM
        self.scheduler.add_job(
            func=self._cleanup_expired_leaves,
            trigger=CronTrigger(hour=0, minute=5),
            id='leave_cleanup',
            name='Expired Leaves Cleanup',
            replace_existing=True
        )

        if settings.auto_checkout_enabled:
            # Schedule daily auto-checkout at specified time
            checkout_hour = settings.auto_checkout_time.hour
            checkout_minute = settings.auto_checkout_time.minute

            self.scheduler.add_job(
                func=self._perform_auto_checkout,
                trigger=CronTrigger(hour=checkout_hour, minute=checkout_minute),
                id='auto_checkout',
                name='Daily Auto Checkout',
                replace_existing=True
            )

            if settings.email_reminders_enabled:
                # Schedule email reminders before checkout
                reminder_minutes = settings.reminder_time_before_checkout
                reminder_time = (datetime.combine(datetime.today(), settings.auto_checkout_time) -
                               timedelta(minutes=reminder_minutes)).time()

                self.scheduler.add_job(
                    func=self._send_checkout_reminders,
                    trigger=CronTrigger(hour=reminder_time.hour, minute=reminder_time.minute),
                    id='checkout_reminders',
                    name='Checkout Email Reminders',
                    replace_existing=True
                )

    def _perform_auto_checkout(self):
        """Automatically check out users who are still checked in"""
        with self.app.app_context():
            try:
                current_time = get_nepal_time()

                # Find all users who are currently checked in (no check_out time)
                checked_in_users = Attendance.query.filter(
                    Attendance.check_out.is_(None),
                    Attendance.check_in >= current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                ).all()

                for attendance in checked_in_users:
                    # Auto-checkout the user
                    attendance.check_out = current_time

                    # Calculate final status
                    user = attendance.user
                    attendance.status = AttendanceService.calculate_status(
                        attendance.check_in, attendance.check_out, user.role
                    )

                    # Calculate overtime if applicable
                    duration = (attendance.check_out - attendance.check_in).total_seconds() / 3600
                    if duration > 9:  # More than 9 hours worked
                        attendance.overtime_hours = duration - 9

                    current_app.logger.info(f"Auto-checked out user {user.id} ({user.profile.full_name if user.profile else user.email})")

                db.session.commit()
                current_app.logger.info(f"Auto-checkout completed for {len(checked_in_users)} users")

            except Exception as e:
                current_app.logger.error(f"Error during auto-checkout: {e}")
                db.session.rollback()

    def _send_checkout_reminders(self):
        """Send email reminders to users who are still checked in"""
        with self.app.app_context():
            try:
                current_time = get_nepal_time()

                # Find all users who are currently checked in
                checked_in_users = Attendance.query.filter(
                    Attendance.check_out.is_(None),
                    Attendance.check_in >= current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                ).join(User).all()

                reminder_count = 0
                for attendance in checked_in_users:
                    user = attendance.user
                    if user.profile and user.profile.personal_email:
                        # Send reminder email
                        send_email(
                            subject="EMS Reminder: Please Check Out",
                            recipient=user.profile.personal_email,
                            template="emails/checkout_reminder",
                            user=user,
                            attendance=attendance
                        )
                        reminder_count += 1

                current_app.logger.info(f"Sent checkout reminders to {reminder_count} users")

            except Exception as e:
                current_app.logger.error(f"Error sending checkout reminders: {e}")

    def _cleanup_expired_leaves(self):
        """Automatically reject pending leave requests whose start dates have passed."""
        with self.app.app_context():
            try:
                today = get_nepal_time().date()
                
                # Find all LeaveRequests that are 'pending' but the start date is in the past
                expired_leaves = LeaveRequest.query.filter(
                    LeaveRequest.status == 'pending',
                    LeaveRequest.start_date < today
                ).all()

                for leave in expired_leaves:
                    leave.status = 'rejected'
                    
                    # Add an audit trace
                    log = AuditLog(
                        user_id=leave.user_id,
                        action=f"Auto-Rejected Leave Request (ID: {leave.id}) because the start date passed without Admin approval.",
                        ip_address="SYSTEM_SCHEDULER"
                    )
                    db.session.add(log)
                    
                    current_app.logger.info(f"Cleaned up expired leave request for User {leave.user_id}")

                if expired_leaves:
                    db.session.commit()
                    current_app.logger.info(f"Cleaned up {len(expired_leaves)} expired leave requests.")

            except Exception as e:
                current_app.logger.error(f"Error during leave cleanup: {e}")
                db.session.rollback()

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("Scheduler started")  # Use print instead of logger since context might not be available

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Scheduler stopped")

    def restart(self):
        """Restart the scheduler with updated settings"""
        with self.app.app_context():
            self.stop()
            self._setup_jobs()
        self.start()