import pandas as pd
import os
from database.models import User, EmployeeProfile
from extensions import db

class ExcelSyncService:
    @staticmethod
    def sync_role_to_excel(role):
        """
        Query all users of a specific role, flatten into a list of dicts,
        and save to database/{role}.xlsx.
        """
        # Ensure the 'database' directory exists
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database')
        if not os.path.exists(db_path):
            os.makedirs(db_path)
            
        file_path = os.path.join(db_path, f"{role}.xlsx")
        
        # Query users with their profiles
        users = User.query.filter_by(role=role).all()
        
        data = []
        for user in users:
            p = user.profile
            if not p:
                continue
                
            row = {
                'Login Email': user.email,
                'Full Name': p.full_name,
                'Staff ID': p.employee_id,
                'Role': user.role.capitalize(),
                'Department': p.department or 'N/A',
                'Designation': p.designation or 'N/A',
                'Joining Date': p.joining_date.strftime('%Y-%m-%d') if p.joining_date else 'N/A',
                'Phone': p.phone or 'N/A',
                'Personal Email': p.personal_email or 'N/A',
                'Base Salary/Fee': p.base_salary or 0.0,
                'Paid/HRA': p.hra or 0.0,
                'Status': 'Active' if user.is_active else 'Inactive',
                'Workshop Status': p.workshop_status or 'N/A',
                'Payment Status': p.payment_status or 'N/A',
                'Pan Number': p.pan_number or 'N/A',
                'Bank Account': p.bank_account or 'N/A'
            }
            data.append(row)
            
        if not data:
            # Create an empty file with headers if no data
            df = pd.DataFrame(columns=[
                'Login Email', 'Full Name', 'Staff ID', 'Role', 'Department', 
                'Designation', 'Joining Date', 'Phone', 'Personal Email', 
                'Base Salary/Fee', 'Paid/HRA', 'Status', 'Workshop Status', 
                'Payment Status', 'Pan Number', 'Bank Account'
            ])
        else:
            df = pd.DataFrame(data)
            
        # Write to Excel
        try:
            df.to_excel(file_path, index=False, engine='openpyxl')
            print(f"Successfully synced {role} to {file_path}")
            return True
        except Exception as e:
            print(f"Error syncing {role} to Excel: {e}")
            return False

    @staticmethod
    def sync_all():
        """
        Helper to sync all three primary roles.
        """
        ExcelSyncService.sync_role_to_excel('employee')
        ExcelSyncService.sync_role_to_excel('intern')
        ExcelSyncService.sync_role_to_excel('student')
