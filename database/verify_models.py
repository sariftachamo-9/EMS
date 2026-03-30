from app import create_app
from extensions import db
from .models import ContactQuery

app = create_app('development')
with app.app_context():
    q = ContactQuery()
    fields = ['is_anonymous', 'phone', 'subject', 'description', 'user_id']
    for field in fields:
        print(f"{field}: {hasattr(q, field)}")
