from extensions import db
from database.models import LeaveRequest
from datetime import timedelta

class LeaveService:
    @staticmethod
    def calculate_leave_balance(user_id, annual_allowance=15.0):
        """
        Calculates the remaining leave balance for a user.
        Excludes Saturdays from the duration of approved leaves.
        """
        approved_leaves = LeaveRequest.query.filter_by(
            user_id=user_id, status='approved'
        ).all()
        
        used_leaves = 0.0
        for lr in approved_leaves:
            curr = lr.start_date
            while curr <= lr.end_date:
                # 5 = Saturday in Python's weekday() (Monday is 0, Sunday is 6)
                if curr.weekday() != 5:
                    used_leaves += 1.0
                curr += timedelta(days=1)
                
        balance = annual_allowance - used_leaves
        return max(0.0, balance)
