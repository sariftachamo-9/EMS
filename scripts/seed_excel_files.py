import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from utils.excel_sync import ExcelSyncService

def seed_excel():
    print("--- Initializing Excel Staff Files ---")
    app = create_app('development')
    with app.app_context():
        ExcelSyncService.sync_all()
    print("--- Initialization Complete ---")

if __name__ == "__main__":
    seed_excel()
