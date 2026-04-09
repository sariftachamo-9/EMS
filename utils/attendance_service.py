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
        Optimized: Fetches all records in the period in ONE query instead of 111+ queries.
        """
        # Fetch all attendance records for the period in bulk
        records = Attendance.query.filter_by(user_id=user_id).filter(
            Attendance.check_in >= datetime.combine(start_date, datetime.min.time()),
            Attendance.check_in <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Index records by date for O(1) lookup in memory
        record_map = {att.check_in.date(): att for att in records}
        
        has_changes = False
        # Calculate days until the first Saturday in the range
        days_to_first_sat = (5 - start_date.weekday() + 7) % 7
        curr = start_date + timedelta(days=days_to_first_sat)
        
        while curr <= end_date:
            # We are now guaranteed to be on a Saturday
            existing = record_map.get(curr)
            friday = curr - timedelta(days=1)
            sunday = curr + timedelta(days=1)
            
            friday_att = record_map.get(friday)
            sunday_att = record_map.get(sunday)
            
            is_fri_present = friday_att and friday_att.status not in ['absent', None]
            is_sun_present = sunday_att and sunday_att.status not in ['absent', None]
            
            calculated_status = 'present' if (is_fri_present or is_sun_present) else 'absent'
            is_weekend = (calculated_status == 'present')
            
            if existing:
                if existing.status != calculated_status:
                    existing.status = calculated_status
                    existing.is_weekend = is_weekend
                    has_changes = True
            else:
                dummy_time = datetime.combine(curr, datetime.min.time()).replace(hour=12)
                weekend_att = Attendance(
                    user_id=user_id, 
                    check_in=dummy_time, 
                    check_out=dummy_time, 
                    status=calculated_status, 
                    is_weekend=is_weekend
                )
                db.session.add(weekend_att)
                has_changes = True
            
            curr += timedelta(days=7) # Jump to next Saturday
        
        if has_changes:
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
            
        # Count present days in DB (Optimized query with raw datetime ranges for indexing)
        start_of_month_dt = datetime.combine(first_of_month, datetime.min.time())
        end_of_period_dt = datetime.combine(current_date, datetime.max.time())
        
        present_count = Attendance.query.filter_by(user_id=user_id).filter(
            Attendance.check_in >= start_of_month_dt,
            Attendance.check_in <= end_of_period_dt,
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
        import os, time, subprocess
        # Moved to database/ folder to avoid triggering Flask's reloader in the root folder.
        db_dir = os.path.join(self.app.root_path, 'database')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        lock_file = os.path.join(db_dir, 'attendance_monitor.lock')
        
        def is_pid_alive(pid):
            if os.name == 'posix':
                # POSIX way to check for process existence without killing it
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False
            else:
                try:
                    # Windows fallback check
                    output = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}', '/NH'], 
                                                  stderr=subprocess.STDOUT, 
                                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0).decode()
                    return str(pid) in output
                except Exception:
                    return False

        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
                if not is_pid_alive(old_pid):
                    # print(f"Stale monitor lock found (PID {old_pid} is dead). Cleaning up...")
                    try: os.remove(lock_file)
                    except: pass
                else:
                    # print(f"Attendance Monitor already running under PID {old_pid}. Exiting.")
                    return
            except (ValueError, OSError):
                # File corrupted or locked, try to remove it
                try: 
                    os.remove(lock_file)
                except:
                    return

        try:
            # Atomic creation to prevent race condition
            self.lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.lock_fd, str(os.getpid()).encode())
        except OSError:
            # print("Could not acquire monitor lock. Another instance may have just started.")
            return

        print(f"Attendance Monitor started successfully (Lock acquired by PID {os.getpid()}).")
        while True:
            with self.app.app_context():
                try:
                    pass  # Monitor running (heartbeat removed)
                except Exception as e:
                    print(f"Monitor error: {e}")
            time.sleep(60) # Run every minute


