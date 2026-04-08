from extensions import db
from database.models import LeaveRequest
from datetime import timedelta

class LeaveService:
    @staticmethod
    def calculate_leave_balance(user_id, annual_allowance=15.0):
        """
        Calculates the remaining leave balance for a user.
        Excludes Saturdays from the duration of approved leaves using date arithmetic.
        """
        approved_leaves = LeaveRequest.query.filter_by(
            user_id=user_id, status='approved'
        ).all()
        
        used_leaves = 0.0
        for lr in approved_leaves:
            # Mathematical calculation to exclude Saturdays
            days_diff = (lr.end_date - lr.start_date).days + 1
            if days_diff <= 0: continue
            
            # Count the number of Saturdays in range
            start_weekday = lr.start_date.weekday() # 0=Monday, 5=Saturday
            num_weeks = days_diff // 7
            remaining_days = days_diff % 7
            
            saturdays = num_weeks
            # Check if Saturday is in the remaining partial week
            for i in range(remaining_days):
                if (start_weekday + i) % 7 == 5:
                    saturdays += 1
            
            used_leaves += (days_diff - saturdays)
                
        balance = annual_allowance - used_leaves
        return max(0.0, float(balance))
