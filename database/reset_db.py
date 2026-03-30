from app import create_app
from extensions import db
import os

app = create_app('development')
db_path = os.path.join(app.root_path, 'database', 'ems.db')

with app.app_context():
    print(f"Dropping all tables from {db_path}...")
    db.drop_all()
    print("Recreating all tables based on latest models...")
    db.create_all()
    print("Database reset complete.")

# Now run the original seed logic
print("Running seed script to restore default data...")
from . import seed
