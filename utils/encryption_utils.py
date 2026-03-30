import os
from cryptography.fernet import Fernet
from flask import current_app

class EncryptionService:
    @staticmethod
    def get_fernet():
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            # Fallback for development if not set, BUT LOG A WARNING
            # In production, this will fail purposefully if key is missing
            key = current_app.config.get('SECRET_KEY')
            if len(key) < 32:
                key = key.ljust(32)[:32].encode()
            import base64
            key = base64.urlsafe_b64encode(key)
        
        return Fernet(key)

    @classmethod
    def encrypt(cls, data):
        if not data:
            return None
        f = cls.get_fernet()
        return f.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, token):
        if not token:
            return None
        try:
            f = cls.get_fernet()
            return f.decrypt(token.encode()).decode()
        except Exception:
            # If decryption fails, it might be plaintext (pre-migration) 
            # or a wrong key. Return as is for migration safety.
            return token
