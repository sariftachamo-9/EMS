import sys
import os
sys.path.append(os.getcwd())

from app import create_app
from extensions import db
from database.models import User, EmployeeProfile, OfficeSettings
from werkzeug.security import generate_password_hash
from datetime import date

import os

app = create_app('development')

with app.app_context():
    # Ensure database directory exists
    db_dir = os.path.join(app.root_path, 'database')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Create tables
    db.create_all()
    
    # Add/Update Admin User
    admin_email = 'admin@ems.com'
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash('AdmiN@369'),
            role='admin'
        )
        db.session.add(admin)
        db.session.flush() # To get admin.id
        
        profile = EmployeeProfile(
            user_id=admin.id,
            full_name='System Administrator',
            employee_id='EMS-001',
            department='Management',
            designation='Admin',
            joining_date=date(2023, 1, 1),
            base_salary=100000
        )
        db.session.add(profile)
    else:
        # Update password for safety if it exists
        admin.password_hash = generate_password_hash('AdmiN@369')
        
    # Add/Update Other Roles
    other_roles = [
        {'email': 'employee@ems.com', 'role': 'employee', 'name': 'Generic Employee', 'id': 'EMP-001', 'pass': 'EmployeE@123'},
        {'email': 'intern@ems.com', 'role': 'intern', 'name': 'Generic Intern', 'id': 'ITN-001', 'pass': 'InterN@456'},
        {'email': 'student@ems.com', 'role': 'student', 'name': 'Generic Student', 'id': 'STD-001', 'pass': 'StudenT@789'}
    ]
    
    for r_data in other_roles:
        user = User.query.filter_by(email=r_data['email']).first()
        if not user:
            user = User(
                email=r_data['email'],
                password_hash=generate_password_hash(r_data['pass']),
                role=r_data['role']
            )
            db.session.add(user)
            db.session.flush()
            
            profile = EmployeeProfile(
                user_id=user.id,
                full_name=r_data['name'],
                employee_id=r_data['id'],
                department='General',
                designation=r_data['role'].capitalize(),
                joining_date=date(2023, 1, 1),
                base_salary=50000
            )
            db.session.add(profile)
        else:
            user.password_hash = generate_password_hash(r_data['pass'])

    # Add Office Settings
    if not OfficeSettings.query.first():
        settings = OfficeSettings(
            latitude=27.7172,
            longitude=85.3240,
            radius=100
        )
        db.session.add(settings)
        
    db.session.commit()
    print("Database seeded successfully with all roles. Password: AdmiN@369")
