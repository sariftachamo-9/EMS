import os
import json
from app import create_app
from extensions import db
from .models import User, EmployeeProfile

def extract_payroll_data():
    app = create_app('development')
    with app.app_context():
        # Query all users who are not admins
        users = User.query.filter(User.role != 'admin').all()
        
        payroll_list = []
        
        for user in users:
            profile = user.profile
            if not profile:
                continue
                
            monthly_salary = profile.base_salary / 12 if profile.base_salary else 0
            
            data = {
                "Full Name": profile.full_name,
                "Role": user.role.capitalize(),
                "Annual Salary": profile.base_salary,
                "Monthly Base Salary": round(monthly_salary, 2),
                "HRA": profile.hra,
                "Transport Allowance": profile.transport_allowance,
                "Other Allowances": profile.other_allowances,
                "Tax Deduction": getattr(profile, 'tax_deduction', 0.0),
                "Insurance Deduction": getattr(profile, 'insurance_deduction', 0.0),
                "Other Deductions": getattr(profile, 'other_deductions', 0.0),
                "Overtime Rate": profile.overtime_rate
            }
            payroll_list.append(data)
            
        # Save to JSON
        json_path = os.path.join(os.path.dirname(__file__), 'payroll_data.json')
        with open(json_path, 'w') as f:
            json.dump(payroll_list, f, indent=4)
            
        # Generate Markdown Table for PAYROLL_DETAILS.md
        md_content = "# Payroll Data Extraction Summary\n\n"
        md_content += "| Full Name | Role | Annual Salary | Monthly Base | HRA | Transport | Others | Tax | Insurance | Deductions | OT Rate |\n"
        md_content += "|-----------|------|---------------|--------------|-----|-----------|--------|-----|-----------|------------|---------|\n"
        
        for p in payroll_list:
            md_content += f"| {p['Full Name']} | {p['Role']} | {p['Annual Salary']} | {p['Monthly Base Salary']} | {p['HRA']} | {p['Transport Allowance']} | {p['Other Allowances']} | {p['Tax Deduction']} | {p['Insurance Deduction']} | {p['Other Deductions']} | {p['Overtime Rate']} |\n"
            
        with open('PAYROLL_DETAILS.md', 'w') as f:
            f.write(md_content)
            
        print(f"Successfully extracted data for {len(payroll_list)} staff members.")
        print("Generated files: payroll_data.json, PAYROLL_DETAILS.md")

if __name__ == "__main__":
    extract_payroll_data()
