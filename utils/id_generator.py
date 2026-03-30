from database.models import User, EmployeeProfile

def generate_staff_id(role, department):
    """
    Generates a staff ID based on role and department.
    Pattern: [Prefix]-[DeptCode]-[00X]
    """
    # 1. Map Prefix
    if role == 'employee':
        prefix = "EM"
    elif role == 'intern':
        prefix = "TRN"
    elif role == 'student':
        prefix = "ST"
    else:
        prefix = "GEN"
    
    # 2. Map DeptCode
    dept_map = {
        "Finance": "FIN",
        "Marketing": "MKT",
        "Engineer": "ENGG",
        "IT": "IT",
        "HR": "HR"
    }
    dept_code = dept_map.get(department, "GEN")
    
    # 3. Find latest sequence
    pattern = f"{prefix}-{dept_code}-"
    latest_profile = EmployeeProfile.query.filter(
        EmployeeProfile.employee_id.like(f"{pattern}%")
    ).order_by(EmployeeProfile.employee_id.desc()).first()
    
    if latest_profile:
        try:
            # Extract number from EM-FIN-001
            last_num_str = latest_profile.employee_id.split('-')[-1]
            next_num = int(last_num_str) + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
        
    # 4. Format with leading zeros
    return f"{pattern}{str(next_num).zfill(3)}"
