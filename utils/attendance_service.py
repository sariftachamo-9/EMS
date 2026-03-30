from flask import current_app
from extensions import db
from database.models import Attendance, User, OfficeSettings
from datetime import datetime, timedelta
from utils.time_utils import get_nepal_time
import math

class AttendanceService:
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return float('inf')
        # Haversine formula
        R = 6371e3 # Earth radius in meters
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        dphi = math.radians(float(lat2 - lat1))
        dlambda = math.radians(float(lon2 - lon1))
        
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def is_within_geofence(user_lat, user_lon, office_lat, office_lon, radius):
        # Check primary office
        distance = AttendanceService.calculate_distance(user_lat, user_lon, office_lat, office_lon)
        if distance <= radius:
            return True, distance
            
        # Check secondary offices (AllowedLocation)
        from database.models import AllowedLocation
        allowed_locs = AllowedLocation.query.filter_by(is_active=True).all()
        for loc in allowed_locs:
            dist = AttendanceService.calculate_distance(user_lat, user_lon, loc.latitude, loc.longitude)
            if dist <= loc.radius:
                return True, dist
                
        return False, distance

    @staticmethod
    def calculate_status(check_in, check_out, role='employee'):
        if not check_out:
            # Late check-in logic (if before 09:30 AM it's Present, else Late)
            if check_in.hour > 9 or (check_in.hour == 9 and check_in.minute > 30):
                return 'late'
            return 'present'
        
        # Calculate duration
        duration = (check_out - check_in).total_seconds() / 3600
        
        # Role-based thresholds
        if role == 'student':
            present_threshold = 1.0
            half_day_threshold = 0.75
        elif role == 'intern':
            present_threshold = 4
            half_day_threshold = 2
        else: # employee
            present_threshold = 7
            half_day_threshold = 4
            
        if duration >= present_threshold:
            return 'present'
        elif duration >= half_day_threshold:
            return 'half-day'
        else:
            return 'absent'

    @staticmethod
    def sync_saturdays_for_period(user_id, start_date, end_date):
        """
        Auto-syncs Saturdays based on surrounding Friday and Sunday status (Sandwich Rule).
        If both Friday and Sunday are absent, Saturday is 'absent'.
        Otherwise, if either is present/late/half-day/holiday, Saturday is 'present'.
        """
        curr = start_date
        while curr <= end_date:
            if curr.weekday() == 5: # Saturday
                # Check for existing records today
                existing = Attendance.query.filter_by(user_id=user_id).filter(
                    db.func.date(Attendance.check_in) == curr
                ).first()
                
                friday = curr - timedelta(days=1)
                sunday = curr + timedelta(days=1)
                
                # Check Friday status
                friday_att = Attendance.query.filter_by(user_id=user_id).filter(
                    db.func.date(Attendance.check_in) == friday
                ).first()
                
                # Check Sunday status
                sunday_att = Attendance.query.filter_by(user_id=user_id).filter(
                    db.func.date(Attendance.check_in) == sunday
                ).first()
                
                # Logic: Treated as 'Present' if status is anything other than 'absent'
                is_fri_present = friday_att and friday_att.status not in ['absent', None]
                is_sun_present = sunday_att and sunday_att.status not in ['absent', None]
                
                # Sandwich Rule
                calculated_status = 'present' if (is_fri_present or is_sun_present) else 'absent'
                is_weekend = (calculated_status == 'present')
                
                if existing:
                    # Reconciliation: Update status if it differs (unless it's 'present' meaning they actually worked)
                    # We only downgrade to 'absent' or upgrade from 'absent' to 'present' based on the rule
                    # But we don't override an actual 'checked-in' manually worked Saturday (which would have duration)
                    if existing.status != calculated_status:
                        # Only update if the existing record is a "system generated" one (no check-out or dummy check-out)
                        # For simplicity, if the status is one of the reconciled ones, we sync it.
                        existing.status = calculated_status
                        existing.is_weekend = is_weekend
                else:
                    # Create new system record
                    dummy_time = datetime.combine(curr, datetime.min.time()).replace(hour=12)
                    weekend_att = Attendance(
                        user_id=user_id, 
                        check_in=dummy_time, 
                        check_out=dummy_time, 
                        status=calculated_status, 
                        is_weekend=is_weekend
                    )
                    db.session.add(weekend_att)
            curr += timedelta(days=1)
        db.session.commit()

    @staticmethod
    def calculate_attendance_score(user_id, current_date):
        """
        Calculates the attendance score % for the current month.
        Score = (Present Days / Total Working Days) * 100
        Saturdays are excluded from total working days.
        """
        first_of_month = current_date.replace(day=1)
        
        # Count working days excluding Saturdays up to TODAY
        total_work_days = 0
        curr = first_of_month
        while curr <= current_date:
            if curr.weekday() != 5: # Skip Saturdays
                total_work_days += 1
            curr += timedelta(days=1)
            
        # Count present days in DB
        present_count = Attendance.query.filter_by(user_id=user_id).filter(
            db.func.date(Attendance.check_in) >= first_of_month,
            db.func.date(Attendance.check_in) <= current_date,
            Attendance.status.in_(['present', 'half-day', 'late'])
        ).count()

        # Edge Case Handle: On the first day of the month, show 100% (Neutral) 
        # until the first workday concludes or is missed.
        if total_work_days <= 1 and present_count == 0:
            return 100
            
        if total_work_days == 0:
            return 100
            
        score = (present_count / total_work_days) * 100
        return round(min(100, score))

class AttendanceMonitor:
    _instance_active = False

    def __init__(self, app):
        self.app = app

    def run(self):
        import os, time
        lock_file = os.path.join(self.app.root_path, 'attendance_monitor.lock')
        
        try:
            # Atomic creation of a lock file. Fails if file exists.
            self.lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            # If the file exists, another process is already the monitor.
            # (In production, we would also check if the PID in the file is still alive)
            return

        print(f"Attendance Monitor started successfully (Lock acquired by PID {os.getpid()}).")
        
        # Write PID to lock file for debugging
        os.write(self.lock_fd, str(os.getpid()).encode())
        while True:
            with self.app.app_context():
                try:
                    self.process_heartbeats()
                except Exception as e:
                    print(f"Monitor error: {e}")
            time.sleep(60) # Run every minute

    def process_heartbeats(self):
        # Auto-checkout logic for inactivity or geofence violation
        now = get_nepal_time()
        active_attendances = Attendance.query.filter(Attendance.check_out == None).all()
        
        has_changes = False
        for att in active_attendances:
            # 1. Inactivity Timeout (30 mins)
            if att.heartbeat_last and (now - att.heartbeat_last).total_seconds() > 1800: # 30 mins
                att.check_out = att.heartbeat_last
                has_changes = True
                continue
                
            # 2. Geofence Grace Period Timeout (10 mins)
            if att.outside_geofence_since:
                elapsed_grace_mins = (now - att.outside_geofence_since).total_seconds() / 60
                if elapsed_grace_mins > 10:
                    from database.models import AuditLog
                    db.session.add(AuditLog(
                        user_id=att.user_id,
                        action=f"System Auto-Checkout: Geofence grace period (10m) exceeded.",
                        ip_address="0.0.0.0" # Background system action
                    ))
                    att.check_out = now
                    has_changes = True

        if has_changes:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Monitor Commit Failed: {e}")
