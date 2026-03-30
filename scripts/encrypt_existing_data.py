import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from database.models import EmployeeProfile
from utils.encryption_utils import EncryptionService

def encrypt_data():
    app = create_app('development')
    with app.app_context():
        print("Scanning for unencrypted PII data...")
        profiles = EmployeeProfile.query.all()
        count = 0
        for profile in profiles:
            # The custom TypeDecorator automatically handles encryption on assignment
            # We just need to trigger a 'save' for each record
            # We read the values (which might return plaintext if decryption fails)
            # and re-assign them (which triggers encryption)
            
            p_email = profile.personal_email
            p_phone = profile.phone
            p_pan = profile.pan_number
            p_bank = profile.bank_account
            
            # Re-assigning triggers the 'process_bind_param' in TypeDecorator
            profile.personal_email = p_email
            profile.phone = p_phone
            profile.pan_number = p_pan
            profile.bank_account = p_bank
            
            count += 1
            
        db.session.commit()
        print(f"Success: Processed {count} profiles.")

if __name__ == '__main__':
    encrypt_data()
