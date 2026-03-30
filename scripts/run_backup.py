import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app import create_app
from utils.backup_service import BackupService

def main():
    print("Starting system backup...")
    app = create_app('development')
    
    with app.app_context():
        success, message = BackupService.run_full_backup()
        if success:
            print("\033[92mSUCCESS:\033[0m")
            print(message)
        else:
            print("\033[91mFAILED:\033[0m")
            print(message)

if __name__ == '__main__':
    main()
