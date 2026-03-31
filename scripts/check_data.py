import os
from app import create_app
from extensions import db
from database.models import Attendance, User, AuditLog
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    print("= Attendance Summary =")
    atts = Attendance.query.all()
    if not atts:
        print("No attendance records found.")
    else:
        dates = sorted(list(set([a.check_in.date() for a in atts])))
        for d in dates:
            count = Attendance.query.filter(db.func.date(Attendance.check_in) == d).count()
            print(f"{d}: {count} records")

    print("\n= User Accounts =")
    users = User.query.all()
    for u in users:
        print(f"User: {u.username} ({u.role}), Created: {u.created_at.date() if u.created_at else 'Unknown'}")

    print("\n= Recent Audit Logs =")
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    for l in logs:
        print(f"{l.timestamp}: {l.action}")
