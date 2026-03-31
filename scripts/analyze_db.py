import os
import sys
from datetime import datetime, timedelta

# Add current dir to path to find app.py
sys.path.append(os.getcwd())

from app import create_app
from extensions import db
from database.models import Attendance, AuditLog, User

app = create_app()
with app.app_context():
    print("= Database Record Analysis =")
    
    # 1. Attendance Records
    atts = Attendance.query.all()
    if atts:
        dates = sorted(list(set([a.check_in.date() for a in atts])))
        print(f"Attendance Date Range: {dates[0]} to {dates[-1]}")
        print(f"Total Attendance Records: {len(atts)}")
        for d in dates:
            count = Attendance.query.filter(db.func.date(Attendance.check_in) == d).count()
            print(f"  {d}: {count} records")
    else:
        print("No attendance records found.")
        
    # 2. Audit Logs
    logs = AuditLog.query.all()
    if logs:
        dates = sorted(list(set([l.timestamp.date() for l in logs])))
        print(f"\nAuditLog Date Range: {dates[0]} to {dates[-1]}")
        print(f"Total AuditLog Records: {len(logs)}")
        for d in dates:
             count = AuditLog.query.filter(db.func.date(AuditLog.timestamp) == d).count()
             print(f"  {d}: {count} records")
    else:
        print("No audit logs found.")

    # 3. User Accounts
    users = User.query.all()
    print(f"\nTotal Users: {len(users)}")
    roles = {}
    for u in users:
        roles[u.role] = roles.get(u.role, 0) + 1
    for role, count in roles.items():
        print(f"  {role}: {count}")

    # 4. Check for specifically 6 days ago (March 25, 2026)
    target_date = (datetime.now() - timedelta(days=6)).date()
    # Corrected target date calculation: Current local time is 2026-03-31
    # So 6 days before is March 25.
    print(f"\nTarget Date (6 days ago): {target_date}")
    
    match_atts = Attendance.query.filter(db.func.date(Attendance.check_in) == target_date).count()
    match_logs = AuditLog.query.filter(db.func.date(AuditLog.timestamp) == target_date).count()
    
    print(f"  Attendance on {target_date}: {match_atts}")
    print(f"  AuditLogs on {target_date}: {match_logs}")
