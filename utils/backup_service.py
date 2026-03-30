import os
import shutil
import pandas as pd
from datetime import datetime
from extensions import db
from database.models import User, Attendance, EmployeeProfile, LeaveRequest, OfficeSettings

class BackupService:
    @staticmethod
    def get_backup_dir():
        backup_dir = os.path.join(os.getcwd(), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        return backup_dir

    @staticmethod
    def take_db_snapshot():
        """Copies the current SQLite database to the backups folder."""
        try:
            db_path = os.path.join(os.getcwd(), 'database', 'ems.db')
            if not os.path.exists(db_path):
                return False, "Database file not found."

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(BackupService.get_backup_dir(), f'ems_backup_{timestamp}.db')
            
            shutil.copy2(db_path, backup_path)
            return True, backup_path
        except Exception as e:
            return False, str(e)

    @staticmethod
    def export_to_excel():
        """Exports major database tables to a multi-sheet Excel file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(BackupService.get_backup_dir(), f'ems_export_{timestamp}.xlsx')

            # Prepare dataframes
            data = {
                'Users': pd.read_sql(db.session.query(User).statement, db.engine),
                'EmployeeProfiles': pd.read_sql(db.session.query(EmployeeProfile).statement, db.engine),
                'Attendance': pd.read_sql(db.session.query(Attendance).statement, db.engine),
                'LeaveRequests': pd.read_sql(db.session.query(LeaveRequest).statement, db.engine),
                'OfficeSettings': pd.read_sql(db.session.query(OfficeSettings).statement, db.engine)
            }

            # Write to Excel
            with pd.ExcelWriter(backup_path, engine='openpyxl') as writer:
                for sheet_name, df in data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            return True, backup_path
        except Exception as e:
            return False, str(e)

    @staticmethod
    def run_full_backup():
        """Runs both DB snapshot and Excel export."""
        db_ok, db_res = BackupService.take_db_snapshot()
        xl_ok, xl_res = BackupService.export_to_excel()
        
        results = []
        if db_ok: results.append(f"DB backup created: {os.path.basename(db_res)}")
        else: results.append(f"DB backup failed: {db_res}")
        
        if xl_ok: results.append(f"Excel export created: {os.path.basename(xl_res)}")
        else: results.append(f"Excel export failed: {xl_res}")
        
        return all([db_ok, xl_ok]), "\n".join(results)
