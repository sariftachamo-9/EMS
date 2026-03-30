import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'ems.db')
if not os.path.exists(db_path):
    # Fallback to root or instance if not found in same dir (though it should be there now)
    db_path = 'database/ems.db'
    if not os.path.exists(db_path):
        db_path = os.path.join('instance', 'ems.db')

print(f"Syncing database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add username to users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(80)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        print("Added username to users")
    except sqlite3.OperationalError as e:
        print(f"Note: {e}")

    # Add new fields to contact_queries
    contact_cols = [
        ("is_anonymous", "BOOLEAN DEFAULT 0"),
        ("phone", "VARCHAR(20)"),
        ("subject", "VARCHAR(200)"),
        ("description", "TEXT"),
        ("user_id", "INTEGER")
    ]
    for col_name, col_type in contact_cols:
        try:
            cursor.execute(f"ALTER TABLE contact_queries ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} to contact_queries")
        except sqlite3.OperationalError:
            print(f"{col_name} already exists in contact_queries")


    # Add new fields to employee_profiles
    profile_cols = [
        ("personal_email", "VARCHAR(120)"),
        ("phone", "VARCHAR(20)"),
        ("overtime_rate", "FLOAT DEFAULT 0.0"),
        ("leave_allowance", "FLOAT DEFAULT 15.0"),
        ("tax_deduction", "FLOAT DEFAULT 0.0"),
        ("insurance_deduction", "FLOAT DEFAULT 0.0"),
        ("other_deductions", "FLOAT DEFAULT 0.0"),
        ("workshop_end_date", "DATE"),
        ("payment_status", "VARCHAR(20)"),
        ("workshop_status", "VARCHAR(20) DEFAULT 'Ongoing'")
    ]
    for col_name, col_type in profile_cols:
        try:
            cursor.execute(f"ALTER TABLE employee_profiles ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} to employee_profiles")
        except sqlite3.OperationalError:
            print(f"{col_name} already exists in employee_profiles")

    # Add snapshot fields to payrolls
    payroll_cols = [
        ("snapshot_base_salary", "FLOAT"),
        ("snapshot_hra", "FLOAT"),
        ("snapshot_transport", "FLOAT"),
        ("overtime_earnings", "FLOAT DEFAULT 0.0"),
        ("lop_deduction", "FLOAT DEFAULT 0.0"),
        ("status", "VARCHAR(20) DEFAULT 'generated'")
    ]

    for col_name, col_type in payroll_cols:
        try:
            cursor.execute(f"ALTER TABLE payrolls ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} to payrolls")
        except sqlite3.OperationalError:
            print(f"{col_name} already exists in payrolls")

    # Create allowed_locations table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                radius INTEGER DEFAULT 100,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        print("Ensured allowed_locations table exists")
    except sqlite3.OperationalError:
        print("Error creating allowed_locations table")

    # Add is_active to notices
    try:
        cursor.execute("ALTER TABLE notices ADD COLUMN is_active BOOLEAN DEFAULT 1")
        print("Added is_active to notices")
    except sqlite3.OperationalError:
        print("is_active already exists in notices")

    # Create login_logs table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80),
                user_id VARCHAR(50),
                role VARCHAR(20),
                latitude FLOAT,
                longitude FLOAT,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Ensured login_logs table exists")
    except sqlite3.OperationalError:
        print("Error creating login_logs table")

    conn.commit()
    print("Database sync complete.")
except Exception as e:
    print(f"Error syncing database: {e}")
