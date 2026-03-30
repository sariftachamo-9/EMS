import math
import secrets
from datetime import datetime, timedelta
from extensions import db
from database.models import VerificationToken

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula to calculate distance in meters"""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
    R = 6371000  # Radius of earth in meters
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2 - lat1))
    dlambda = math.radians(float(lon2 - lon1))
    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_location_token():
    """Generates a secure verification token and stores it in the database."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(seconds=600)
    
    new_token = VerificationToken(
        token=token,
        status='pending',
        expires_at=expires_at
    )
    db.session.add(new_token)
    db.session.commit()
    return token

def verify_token_location(token, lat, lon):
    """Verifies GPS location against office coordinates and updates DB status."""
    # Cleanup expired tokens
    cleanup_tokens()
    
    v_token = VerificationToken.query.filter_by(token=token).first()
    if not v_token or v_token.expires_at < datetime.now():
        return False, "Invalid or expired verification session."
    
    from utils.location_utils import verify_location_access
    is_allowed, msg, dist = verify_location_access(lat, lon)
    
    if is_allowed:
        v_token.status = 'verified'
        v_token.is_verified = True
        v_token.lat = lat
        v_token.lng = lon
        db.session.commit()
        return True, "Location verified successfully."
    
    v_token.status = 'rejected'
    db.session.commit()
    return False, f"Verification failed. You are outside the required range ({int(dist)}m)."

def update_token_status(token, status):
    """Directly set the status of an existing token in the database."""
    v_token = VerificationToken.query.filter_by(token=token).first()
    if v_token:
        v_token.status = status
        if status == 'verified':
            v_token.is_verified = True
        db.session.commit()

def check_token_status(token):
    """Checks the verification status of a token stored in the database."""
    cleanup_tokens()
    v_token = VerificationToken.query.filter_by(token=token).first()
    if not v_token:
        return 'expired'
    return v_token.status

def cleanup_tokens():
    """Removes expired verification tokens from the database."""
    now = datetime.now()
    VerificationToken.query.filter(VerificationToken.expires_at < now).delete()
    db.session.commit()

def verify_ip_fallback(token, user_ip, office_ip):
    """Fallbacks to IP verification if GPS is unavailable."""
    if not token:
        return False
        
    v_token = VerificationToken.query.filter_by(token=token).first()
    if not v_token or v_token.expires_at < datetime.now():
        return False
        
    if user_ip == office_ip and office_ip != "":
        v_token.status = 'verified'
        v_token.is_verified = True
        db.session.commit()
        return True
    return False
