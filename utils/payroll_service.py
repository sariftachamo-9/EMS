from flask import current_app
from extensions import db
from database.models import Payroll, Attendance, EmployeeProfile, User
from datetime import datetime, date
import os
import calendar
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class PayrollService:
    @staticmethod
    def calculate_monthly_salary(user_id, month, year):
        profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return None
        
        # Calculate actual working days (Mon-Fri) in the month
        # Optimized: mathematical calculation instead of a 31-day loop per employee
        _, days_in_month = calendar.monthrange(year, month)
        first_day_weekday, _ = calendar.monthrange(year, month)
        
        # Count weekdays (0-4)
        total_working_days = 0
        for i in range(days_in_month):
            if (first_day_weekday + i) % 7 < 5:
                total_working_days += 1
        
        # If no working days found (not possible), fallback to 22.
        total_days = total_working_days if total_working_days > 0 else 22
        
        # Calculate start and end of month for attendance query
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
            
        attendances = Attendance.query.filter_by(user_id=user_id).filter(
            Attendance.check_in >= start_date,
            Attendance.check_in < end_date
        ).all()
        
        effective_worked_days = 0.0
        for att in attendances:
            # We count 'present', 'late', 'weekend' as full days.
            # 'half-day' as 0.5. 'absent' is handled by the deduction calculation.
            if att.status in ['present', 'late', 'weekend']:
                effective_worked_days += 1.0
            elif att.status == 'half-day':
                effective_worked_days += 0.5
        
        # Calculate daily rate based on actual total working days
        daily_rate = profile.base_salary / total_days
        
        # Absent days are working days not covered by attendance
        absent_days = max(0, total_days - effective_worked_days)
        deductions = absent_days * daily_rate
        
        gross_pay = profile.base_salary + profile.hra + profile.transport_allowance + profile.other_allowances
        net_pay = gross_pay - deductions
        
        return {
            'base_pay': profile.base_salary,
            'gross_pay': gross_pay,
            'deductions': deductions,
            'net_pay': net_pay
        }

    @staticmethod
    def generate_payslip_pdf(payroll_id):
        payroll = Payroll.query.get(payroll_id)
        user = User.query.get(payroll.user_id)
        profile = user.profile
        
        filename = f"payslip_{user.id}_{payroll.month}_{payroll.year}.pdf"
        filepath = os.path.join(current_app.root_path, 'static', 'payslips', filename)
        
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
            
        c = canvas.Canvas(filepath, pagesize=letter)
        c.drawString(100, 750, f"EMS Payslip - {payroll.month}/{payroll.year}")
        c.drawString(100, 730, f"Employee: {profile.full_name}")
        c.drawString(100, 710, f"Base Salary: {payroll.snapshot_base_salary}") # Fixed AttributeError
        c.drawString(100, 690, f"Net Pay: {payroll.net_pay}")
        c.save()
        
        payroll.payslip_path = filename
        db.session.commit()
        return filename
