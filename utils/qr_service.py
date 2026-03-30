import qrcode
import os
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer

class QRService:
    @staticmethod
    def generate_employee_badge(user_id):
        # 1. Check if badge already exists to save resources (Caching)
        filename = f"badge_{user_id}.png"
        filepath = os.path.join(current_app.root_path, 'static', 'images', 'badges', filename)
        if os.path.exists(filepath):
            return filename
            
        from database.models import User
        user = User.query.get(user_id)
        if not user or not user.profile:
            return None
            
        # Create a secure token with user data
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer(current_app.config['SECRET_KEY'])
        token_data = {
            "username": user.profile.full_name,
            "user_id": user.profile.employee_id,
            "role": user.role
        }
        token = s.dumps(token_data)
        
        # Build the full URL
        external_url = os.environ.get('EXTERNAL_URL')
        if external_url:
            verify_url = external_url.rstrip('/') + url_for('qr.auto_login', token=token)
        else:
            verify_url = url_for('qr.auto_login', token=token, _external=True)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(verify_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill='black', back_color='white')
        
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
            
        img.save(filepath)
        return filename
