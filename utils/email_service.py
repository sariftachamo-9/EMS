import os
from flask_mail import Message
from extensions import mail
from flask import render_template, current_app
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {e}")

def send_email(subject, recipient, template, **kwargs):
    app = current_app._get_current_object()
    msg = Message(subject, recipients=[recipient])
    msg.html = render_template(template + '.html', **kwargs)
    
    # Use threading for background email sending
    thr = threading.Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr

def send_otp_email(user, otp):
    # Standard 2FA login (can stay on primary email/personal depending on preference)
    recipient = user.profile.personal_email if (user.profile and user.profile.personal_email) else user.email
    return send_email(
        subject="Your EMS Login OTP",
        recipient=recipient,
        template="emails/otp",
        user=user,
        otp=otp
    )

def send_password_reset_email(user, otp):
    # HIGH SECURITY: Password resets MUST go to personal email only
    recipient = user.profile.personal_email
    if not recipient:
        return False
        
    return send_email(
        subject="EMS Account Recovery - Password Reset OTP",
        recipient=recipient,
        template="emails/password_reset", # Using a specialized template
        user=user,
        otp=otp
    )

def send_leave_notification(admin_email, employee_name, leave_details):
    return send_email(
        subject=f"New Leave Request from {employee_name}",
        recipient=admin_email,
        template="emails/leave_request",
        employee_name=employee_name,
        details=leave_details
    )
def send_notice_broadcast(recipients, notice_title, notice_content):
    if not recipients:
        return
    
    app = current_app._get_current_object()
    
    # Use BCC to send a single batch email securely
    msg = Message(
        subject=f"Announcement: {notice_title}",
        recipients=[current_app.config.get('MAIL_DEFAULT_SENDER')], # Send to self
        bcc=recipients # Hide other recipients
    )
    msg.html = render_template('emails/notice.html', title=notice_title, content=notice_content)
    
    thr = threading.Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr
