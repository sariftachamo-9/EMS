"""
Ensures all database tables exist, including new ones like
VerificationToken and AllowedLocation.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from database.models import (
    User, EmployeeProfile, Attendance, LeaveRequest, Payroll,
    AuditLog, ContactQuery, Notice, OfficeSettings, AllowedLocation,
    BlockedIP, LoginToken, VerificationToken
)

app = create_app('development')

with app.app_context():
    db.create_all()

    # Ensure OfficeSettings row exists
    if not OfficeSettings.query.first():
        settings = OfficeSettings(
            latitude=27.7172,
            longitude=85.3240,
            radius=150  # 150m default – more forgiving for GPS drift
        )
        db.session.add(settings)
        db.session.commit()
        print("✅ OfficeSettings created with default Kathmandu coordinates (27.7172, 85.3240), radius=150m")
    else:
        s = OfficeSettings.query.first()
        print(f"✅ OfficeSettings already exist: lat={s.latitude}, lng={s.longitude}, radius={s.radius}m, office_ip={s.office_ip}")

    print("✅ All tables created/verified successfully.")
    print("\nCurrent AllowedLocations:")
    locs = AllowedLocation.query.all()
    if locs:
        for loc in locs:
            print(f"  - {loc.name}: ({loc.latitude}, {loc.longitude}), radius={loc.radius}m, active={loc.is_active}")
    else:
        print("  (none configured)")
