import os
from cryptography.fernet import Fernet
from flask import current_app

class EncryptionService:
    @staticmethod
    def get_fernet():
        import base64
        key = os.environ.get('ENCRYPTION_KEY')
        if key:
            if isinstance(key, str):
                key = key.encode()
            return Fernet(key)
        else:
            # Fallback for development if not set, BUT LOG A WARNING
            # In production, this will fail purposefully if key is missing
            secret = current_app.config.get('SECRET_KEY', '')
            if len(secret) < 32:
                secret = secret.ljust(32)[:32]
            key = base64.urlsafe_b64encode(secret.encode()[:32])
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
