import os
import sys

# Add the project root to sys.path if running directly
if __name__ == "__main__" or __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user
from extensions import db
from database.models import ContactQuery, User
from utils.time_utils import get_nepal_time

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/display-contact')
def display_contact():
    """Public contact page for general/urgent inquiries."""
    return render_template('shared/display_contact.html')

@contact_bp.route('/contact')
def contact():
    """Internal style contact page with FAQ."""
    return render_template('shared/request_admin.html')

@contact_bp.route('/submit-inquiry', methods=['POST'])
def submit_inquiry():
    """Unified endpoint for all inquiry submissions."""
    # Capture data from form or JSON
    data = request.form if request.form else request.json
    
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    
    # Handle field mapping: query_type -> category, message -> description
    category = data.get('query_type') or data.get('category') or 'General'
    subject = data.get('subject') or f"Inquiry from {name}"
    description = data.get('message') or data.get('description')
    
    if not name or not email or not description:
        flash('Please fill in all required fields.', 'danger')
        return redirect(request.referrer or url_for('contact.display_contact'))

    # Identification
    user_id = None
    is_anonymous = True
    
    if current_user.is_authenticated:
        user_id = current_user.id
        is_anonymous = False
        # Optionally override name/email from profile if not provided
        if not name and current_user.profile:
            name = current_user.profile.full_name
        if not email:
            email = current_user.email

    try:
        new_query = ContactQuery(
            user_id=user_id,
            name=name,
            email=email,
            phone=phone,
            category=category,
            subject=subject,
            description=description,
            is_anonymous=is_anonymous,
            status='open',
            priority='Medium'
        )
        db.session.add(new_query)
        db.session.commit()
        
        flash('Your inquiry has been submitted successfully. Our team will get back to you soon!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting inquiry: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('contact.display_contact'))

@contact_bp.route('/tickets')
def tickets():
    # Only staff/admin should see this in a real app
    queries = ContactQuery.query.order_by(ContactQuery.created_at.desc()).all()
    return render_template('admin/tickets.html', queries=queries)

