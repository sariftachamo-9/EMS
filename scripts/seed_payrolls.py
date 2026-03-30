from app import create_app
from extensions import db
from database.models import User, Payroll
from utils.time_utils import get_nepal_time

app = create_app('development')
with app.app_context():
    users = User.query.filter(User.role != 'admin').all()
    today = get_nepal_time().date()
    current_month = today.month
    current_year = today.year
    count = 0
    
    # Check if we already have some to avoid infinite spam
    if Payroll.query.count() < 10:
        for i in range(1, 4):
            m = current_month - i
            y = current_year
            if m <= 0:
                m += 12
                y -= 1
            for u in users:
                pr = Payroll(
                    user_id=u.id, month=m, year=y,
                    snapshot_base_salary=50000, snapshot_hra=0, snapshot_transport=0,
                    overtime_earnings=0, lop_deduction=0, gross_pay=50000, net_pay=50000, status='Locked'
                )
                db.session.add(pr)
                count += 1
        db.session.commit()
    print(f'Done seeding {count} records.')
