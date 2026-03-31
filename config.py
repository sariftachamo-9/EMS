import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key')
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'database', 'ems.db').replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{db_path}")
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 60}, "pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')
    MAIL_DEBUG = False # Stop verbose SMTP logs in console
    
    # Geofence settings
    OFFICE_LATITUDE = float(os.environ.get('OFFICE_LATITUDE', 27.7172))
    OFFICE_LONGITUDE = float(os.environ.get('OFFICE_LONGITUDE', 85.3240))
    GEOFENCE_RADIUS = int(os.environ.get('GEOFENCE_RADIUS', 100))
    REQUIRE_LOCATION_VERIFICATION = False
    OFFICE_PUBLIC_IP = os.environ.get('OFFICE_PUBLIC_IP', '')
    
    # Session / Security
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Nepal Timezone
    TIMEZONE = os.environ.get('NEPAL_TIMEZONE', 'Asia/Kathmandu')
    
    QR_LOGIN_SALT = os.environ.get('QR_LOGIN_SALT', 'qr-login-salt-34821')
    
    # Rate Limiting
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    
    # Session Version Control (Increase this to force a global logout of all users)
    SESSION_VERSION = os.environ.get('SESSION_VERSION', '1')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    
    # Use Redis for shared Rate Limiting in production (requires Redis server)
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', "redis://localhost:6379")

    @classmethod
    def init_app(cls, app):
        # Mandatory SECRET_KEY check for production
        if os.environ.get('SECRET_KEY') == 'dev-key' or not os.environ.get('SECRET_KEY'):
            raise RuntimeError("CRITICAL SECURITY ERROR: SECRET_KEY must be set in production environment!")

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
