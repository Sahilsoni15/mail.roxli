from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, messaging
import hashlib
import os
import secrets
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True, origins=['https://auth.roxli.in', 'https://account.roxli.in', 'https://mail.roxli.in'])

# JWT Configuration
JWT_SECRET = 'roxli_jwt_secret_key_2024'
TOKEN_EXPIRY = timedelta(days=60)
SESSION_EXPIRY = timedelta(days=60)

# Firebase initialization
try:
    firebase_config = os.environ.get('FIREBASE_CONFIG')
    if firebase_config:
        import json
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        cred = credentials.Certificate('roxli-mail-firebase-adminsdk-fbsvc-68633609db.json')
    
    mail_app = firebase_admin.initialize_app(cred, {
        'databaseURL': os.environ.get('FIREBASE_DATABASE_URL', 'https://roxli-mail-default-rtdb.firebaseio.com/')
    }, name='mail')
    
    print("Firebase mail app initialized successfully")
except Exception as e:
    print(f"Firebase initialization failed: {e}")
    try:
        mail_app = firebase_admin.initialize_app(name='mail')
        print("Firebase mail app initialized with default credentials")
    except:
        print("Failed to initialize Firebase app")
        mail_app = None

# Security headers
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' https://auth.roxli.in https://account.roxli.in https://mail.roxli.in https://fcm.googleapis.com https://firebaseinstallations.googleapis.com; object-src 'none'; base-uri 'self';"
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', 'https://mail.roxli.in')
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

def verify_token(token):
    """Verify JWT token"""
    try:
        import hmac
        import hashlib
        import base64
        import json
        import time
        
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_encoded, payload_encoded, signature_encoded = parts
        
        # Verify signature
        message = f"{header_encoded}.{payload_encoded}"
        expected_signature = hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
        expected_signature_encoded = base64.urlsafe_b64encode(expected_signature).decode().rstrip('=')
        
        if signature_encoded != expected_signature_encoded:
            return None
            
        # Decode payload
        payload_padded = payload_encoded + '=' * (4 - len(payload_encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_padded))
        
        # Check expiration
        if payload.get('exp', 0) < time.time():
            return None
            
        return payload
        
    except Exception:
        return None

def clean_merge_conflicts(text):
    """Remove Git merge conflict markers from text"""
    if not text:
        return text
    
    import re
    # Remove all merge conflict patterns
    text = re.sub(r'<<<<<<< HEAD.*?=======.*?>>>>>>> [a-f0-9]+', '', text, flags=re.DOTALL)
    text = re.sub(r'<<<<<<< HEAD.*?=======', '', text, flags=re.DOTALL)
    text = re.sub(r'=======.*?>>>>>>> [a-f0-9]+', '', text, flags=re.DOTALL)
    text = re.sub(r'<<<<<<< HEAD', '', text)
    text = re.sub(r'=======', '', text)
    text = re.sub(r'>>>>>>> [a-f0-9]+', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_current_user():
    """Get current user from token with session validation"""
    # Check session expiry
    if 'login_time' in session:
        login_time = datetime.fromtimestamp(session['login_time'])
        if datetime.now() - login_time > SESSION_EXPIRY:
            session.clear()
            return None
    
    token = request.cookies.get('roxli_token')
    print(f"DEBUG: Token found: {bool(token)}")
    
    if token:
        try:
            import requests
            print(f"DEBUG: Verifying token with main system...")
            verify_response = requests.post('https://auth.roxli.in/api/verify', 
                                          json={'token': token}, 
                                          timeout=5)
            
            print(f"DEBUG: Verify response status: {verify_response.status_code}")
            if verify_response.status_code == 200:
                verify_data = verify_response.json()
                print(f"DEBUG: Verify data: {verify_data}")
                if verify_data.get('valid'):
                    # Update session activity
                    session['last_activity'] = datetime.now().timestamp()
                    return verify_data['user']
        except Exception as e:
            print(f"User verification error: {e}")
    
    return None

@app.route('/')
def inbox():
    # Check if user has token cookie first
    token = request.cookies.get('roxli_token')
    print(f"DEBUG: Inbox route - Token: {bool(token)}")
    print(f"DEBUG: All cookies: {request.cookies}")
    
    if not token:
        print("DEBUG: No token found, redirecting to login")
        return redirect(url_for('login_required'))
    
    user = get_current_user()
    if not user:
        print("DEBUG: No user found, redirecting to login")
        return redirect(url_for('login_required'))
    return render_template('inbox.html', user=user)

@app.route('/login-required')
def login_required():
    return render_template('login-required.html')

@app.route('/compose')
def compose():
    user = get_current_user()
    if not user:
        return redirect(url_for('login_required'))
    return render_template('compose.html', user=user)

@app.route('/read/<email_id>')
def read_email(email_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login_required'))
    return render_template('read.html', user=user, email_id=email_id)

@app.route('/api/set-token', methods=['POST'])
def set_token():
    """Set authentication token from popup"""
    print("DEBUG: set-token endpoint called")
    data = request.json
    token = data.get('token') if data else None
    print(f"DEBUG: Received token: {bool(token)}")
    
    if not token:
        print("DEBUG: No token provided")
        return jsonify({'error': 'Token required'}), 400
    
    # Verify token with main Roxli system
    try:
        import requests
        print("DEBUG: Verifying token with main system...")
        verify_response = requests.post('https://auth.roxli.in/api/verify', 
                                      json={'token': token}, 
                                      timeout=5)
        
        print(f"DEBUG: Verify response status: {verify_response.status_code}")
        if verify_response.status_code == 200:
            verify_data = verify_response.json()
            print(f"DEBUG: Verify response: {verify_data}")
            if verify_data.get('valid'):
                user = verify_data['user']
                
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['login_time'] = datetime.now().timestamp()
                session.permanent = True
                app.permanent_session_lifetime = SESSION_EXPIRY
                
                resp = jsonify({'success': True, 'user': user})
                resp.set_cookie('roxli_token', token, httponly=True, secure=False, samesite='Lax', path='/', max_age=int(SESSION_EXPIRY.total_seconds()))
                print("DEBUG: Token set successfully")
                return resp
        else:
            print(f"DEBUG: Verify failed with status {verify_response.status_code}")
    except Exception as e:
        print(f"Token verification error: {e}")
    
    print("DEBUG: Token verification failed")
    return jsonify({'error': 'Invalid token'}), 401

@app.route('/api/sent-emails')
def get_sent_emails():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        if not mail_app:
            return jsonify({'error': 'Mail service not available'}), 503
        
        mail_db = db.reference('emails', app=mail_app)
        sent_emails = mail_db.child(user['id']).child('sent').get() or {}
        
        emails = []
        for email_id, email_data in sent_emails.items():
            if email_data.get('from') == user['email']:
                recipient_name = email_data.get('to', '').split('@')[0]
                emails.append({
                    'id': email_id,
                    'to': email_data.get('to', ''),
                    'recipientName': recipient_name,
                    'recipientAvatar': f'https://ui-avatars.com/api/?name={recipient_name.replace(" ", "+")}&background=random&size=40',
                    'subject': email_data.get('subject', ''),
                    'preview': email_data.get('preview', ''),
                    'time': email_data.get('time', ''),
                    'date': email_data.get('date', ''),
                    'timestamp': email_data.get('timestamp', 0)
                })
        
        emails.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return jsonify({'emails': emails})
    except Exception as e:
        print(f"Error fetching sent emails: {e}")
        return jsonify({'emails': []})

@app.route('/api/emails')
def get_emails():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Get emails from mail Firebase for this user only
        mail_db = db.reference('emails', app=mail_app)
        user_emails = mail_db.child(user['id']).child('inbox').get() or {}
        
        emails = []
        for email_id, email_data in user_emails.items():
            # Security check: ensure email belongs to current user
            if email_data.get('to') == user['email'] or email_data.get('from') == user['email']:
                sender_name = email_data.get('senderName', email_data.get('from', '').split('@')[0])
                # Clean merge conflicts from email data
                clean_subject = clean_merge_conflicts(email_data.get('subject', ''))
                clean_preview = clean_merge_conflicts(email_data.get('preview', ''))
                
                emails.append({
                    'id': email_id,
                    'from': email_data.get('from', ''),
                    'senderName': sender_name,
                    'senderAvatar': f'https://ui-avatars.com/api/?name={sender_name.replace(" ", "+")}&background=667eea&color=fff&size=40',
                    'subject': clean_subject,
                    'preview': clean_preview,
                    'time': email_data.get('time', ''),
                    'date': email_data.get('date', ''),
                    'read': email_data.get('read', False),
                    'starred': email_data.get('starred', False),
                    'timestamp': email_data.get('timestamp', 0)
                })
        
        # Sort by timestamp (newest first)
        emails.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Log access
        activity_log = {
            'action': 'emails_accessed',
            'user_id': user['id'],
            'timestamp': datetime.now().timestamp(),
            'ip_address': request.remote_addr,
            'email_count': len(emails)
        }
        mail_db.child('activity_logs').push(activity_log)
        
        return jsonify({'emails': emails})
    except Exception as e:
        print(f"Error fetching emails: {e}")
        return jsonify({'emails': []})

@app.route('/api/send-email', methods=['POST'])
def send_email():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    to = data.get('to', '').strip()
    subject = data.get('subject', '').strip()
    body = (data.get('body') or data.get('message', '')).strip()
    
    # Input validation
    if not to:
        return jsonify({'error': 'Recipient email is required'}), 400
    
    # Email format validation
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, to):
        return jsonify({'error': 'Invalid recipient email format'}), 400
    
    # Content length validation
    if len(subject) > 200:
        return jsonify({'error': 'Subject too long (max 200 characters)'}), 400
    if len(body) > 50000:
        return jsonify({'error': 'Message too long (max 50,000 characters)'}), 400
    
    # Rate limiting check (max 100 emails per hour)
    rate_limit_key = f"email_rate_{user['id']}"
    current_hour = datetime.now().strftime('%Y%m%d%H')
    
    try:
        if not mail_app:
            return jsonify({'error': 'Mail service not available'}), 503
        
        mail_db = db.reference('emails', app=mail_app)
        
        # Check rate limit
        rate_data = mail_db.child('rate_limits').child(rate_limit_key).child(current_hour).get() or 0
        if rate_data >= 100:
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        
        email_id = str(uuid.uuid4())
        timestamp = datetime.now().timestamp()
        
        # Sanitize content
        import html
        safe_subject = html.escape(subject)
        safe_body = html.escape(body)
        
        sender_name = f"{user['firstName']} {user['lastName']}"
        email_data = {
            'id': email_id,
            'from': user['email'],
            'senderName': sender_name,
            'senderAvatar': f'https://ui-avatars.com/api/?name={sender_name.replace(" ", "+")}&background=random&size=40',
            'to': to,
            'subject': safe_subject,
            'body': safe_body,
            'message': safe_body,
            'preview': (safe_body[:100] + '...') if len(safe_body) > 100 else safe_body,
            'timestamp': timestamp,
            'time': datetime.now().strftime('%I:%M %p'),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'read': False,
            'starred': False,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:200]
        }
        
        # Save to sender's sent folder
        mail_db.child(user['id']).child('sent').child(email_id).set(email_data)
        
        # Find recipient by calling auth service
        recipient_id = None
        try:
            import requests
            # Call auth service to find user by email
            auth_response = requests.post('https://auth.roxli.in/api/find-user', 
                                        json={'email': to}, 
                                        timeout=5)
            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                if auth_data.get('found'):
                    recipient_id = auth_data['user']['id']
        except Exception as e:
            print(f"Error finding recipient: {e}")
        
        # If recipient not found in auth system, still save to sent folder
        if not recipient_id:
            print(f"Recipient {to} not found in system, email saved to sent folder only")
        

        
        if recipient_id:
            # Add to recipient's inbox
            mail_db.child(recipient_id).child('inbox').child(email_id).set(email_data)
            
            # Send push notification to recipient
            try:
                send_notification_to_user(
                    recipient_id, 
                    f"New email from {email_data['senderName']}", 
                    safe_subject or '(No subject)',
                    {'email_id': email_id, 'sender': email_data['from'], 'type': 'new_email'}
                )
            except Exception as e:
                print(f"Failed to send notification: {e}")
        
        # Update rate limit
        mail_db.child('rate_limits').child(rate_limit_key).child(current_hour).set(rate_data + 1)
        
        # Log email activity
        activity_log = {
            'action': 'email_sent',
            'user_id': user['id'],
            'email_id': email_id,
            'recipient': to,
            'timestamp': timestamp,
            'ip_address': request.remote_addr
        }
        mail_db.child('activity_logs').push(activity_log)
        
        return jsonify({
            'success': True,
            'message': 'Email sent successfully',
            'emailId': email_id
        })
    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({'error': 'Failed to send email'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    response = jsonify({'success': True})
    response.set_cookie('roxli_token', '', expires=0, path='/')
    return response

@app.route('/api/user')
def get_user():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'user': user})

@app.route('/api/star-email', methods=['POST'])
def star_email():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    email_id = data.get('emailId')
    starred = data.get('starred', True)
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        mail_db.child(user['id']).child('inbox').child(email_id).update({'starred': starred})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Failed to update email'}), 500

@app.route('/api/mark-read', methods=['POST'])
def mark_read():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    email_id = data.get('emailId')
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        mail_db.child(user['id']).child('inbox').child(email_id).update({'read': True})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Failed to update email'}), 500

@app.route('/api/delete-email', methods=['POST'])
def delete_email():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    email_ids = data.get('emailIds', [])
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        for email_id in email_ids:
            mail_db.child(user['id']).child('inbox').child(email_id).delete()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Failed to delete emails'}), 500

@app.route('/api/email/<email_id>')
def get_email(email_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Input validation
    if not email_id or len(email_id) > 100:
        return jsonify({'error': 'Invalid email ID'}), 400
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        
        # Try to get from inbox first
        email_data = mail_db.child(user['id']).child('inbox').child(email_id).get()
        email_folder = 'inbox'
        
        # If not found in inbox, try sent folder
        if not email_data:
            email_data = mail_db.child(user['id']).child('sent').child(email_id).get()
            email_folder = 'sent'
        
        # Security check: ensure email belongs to current user
        if email_data:
            user_owns_email = False
            if email_folder == 'inbox' and email_data.get('to') == user['email']:
                user_owns_email = True
            elif email_folder == 'sent' and email_data.get('from') == user['email']:
                user_owns_email = True
            elif email_data.get('to') == user['email'] or email_data.get('from') == user['email']:
                user_owns_email = True
                
            if not user_owns_email:
                return jsonify({'error': 'Access denied'}), 403
        
        if email_data:
            # Create a mock email if this is the welcome email
            if email_id == 'welcome' or not email_data:
                email = {
                    'id': 'welcome',
                    'from': 'team@roxli.in',
                    'senderName': 'Roxli Mail Team',
                    'senderAvatar': 'https://ui-avatars.com/api/?name=Roxli+Mail+Team&background=1a73e8&color=fff&size=40',
                    'subject': 'Welcome to Roxli Mail! 🎉',
                    'body': f'''<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #1a73e8;">Welcome to Roxli Mail, {user['firstName']}!</h2>
                        <p>Thank you for joining Roxli Mail. Your secure, professional email experience starts here.</p>
                        
                        <h3>🚀 Getting Started:</h3>
                        <ul>
                            <li><strong>Compose:</strong> Click the compose button to send your first email</li>
                            <li><strong>Organize:</strong> Use folders to keep your emails organized</li>
                            <li><strong>Search:</strong> Find emails quickly with our powerful search</li>
                            <li><strong>Account:</strong> Manage your account settings</li>
                        </ul>
                        
                        <h3>🔐 Security Features:</h3>
                        <ul>
                            <li>End-to-end encryption for all emails</li>
                            <li>Multi-account support</li>
                            <li>Device management and security</li>
                            <li>Two-factor authentication available</li>
                        </ul>
                        
                        <p>If you have any questions, feel free to reply to this email.</p>
                        
                        <p>Best regards,<br>
                        <strong>The Roxli Mail Team</strong></p>
                    </div>''',
                    'time': datetime.now().strftime('%I:%M %p'),
                    'date': datetime.now().strftime('%B %d, %Y'),
                    'read': True,
                    'starred': False
                }
            else:
                sender_name = email_data.get('senderName', email_data.get('from', '').split('@')[0])
                # Clean merge conflicts from email content
                clean_subject = clean_merge_conflicts(email_data.get('subject', ''))
                clean_body = clean_merge_conflicts(email_data.get('body', email_data.get('message', '')))
                clean_message = clean_merge_conflicts(email_data.get('message', email_data.get('body', '')))
                
                email = {
                    'id': email_id,
                    'from': email_data.get('from', ''),
                    'to': email_data.get('to', ''),
                    'senderName': sender_name,
                    'senderAvatar': email_data.get('senderAvatar', f'https://ui-avatars.com/api/?name={sender_name.replace(" ", "+")}&background=random&size=40'),
                    'subject': clean_subject,
                    'body': clean_body,
                    'message': clean_message,
                    'time': email_data.get('time', ''),
                    'date': email_data.get('date', ''),
                    'read': email_data.get('read', False),
                    'starred': email_data.get('starred', False),
                    'folder': email_folder
                }
            
            # Mark as read if not already (only for inbox emails)
            if email_folder == 'inbox' and not email_data.get('read', False):
                try:
                    mail_db.child(user['id']).child('inbox').child(email_id).update({'read': True})
                except:
                    pass  # Ignore if update fails
            
            return jsonify({'success': True, 'email': email})
        else:
            return jsonify({'error': 'Email not found'}), 404
    except Exception as e:
        print(f"Error fetching email: {e}")
        return jsonify({'error': 'Failed to fetch email'}), 500

@app.route('/api/send-welcome-email', methods=['POST'])
def send_welcome_email():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        
        # Check if welcome email already exists for this user
        existing_emails = mail_db.child(user['id']).child('inbox').get() or {}
        for email_id, email_data in existing_emails.items():
            if email_data.get('from') == 'team@roxli.in' and 'Welcome' in email_data.get('subject', ''):
                print(f"Welcome email already exists for user {user['id']}")
                return jsonify({'success': True, 'message': 'Welcome email already sent', 'emailId': email_id})
        
        # Create new welcome email
        email_id = 'welcome_' + user['id']
        timestamp = datetime.now().timestamp()
        
        welcome_email = {
            'id': email_id,
            'from': 'team@roxli.in',
            'senderName': 'Roxli Mail Team',
            'senderAvatar': 'https://ui-avatars.com/api/?name=Roxli+Mail+Team&background=1a73e8&color=fff&size=40',
            'to': user['email'],
            'subject': 'Welcome to Roxli Mail! 🎉',
            'body': f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Roxli Mail</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8f9fa; color: #202124;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1a73e8 0%, #667eea 100%); padding: 40px 30px; text-align: center; color: white;">
            <div style="width: 80px; height: 80px; background: rgba(255,255,255,0.2); border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 36px;">
                📧
            </div>
            <h1 style="margin: 0 0 10px 0; font-size: 32px; font-weight: 600;">Welcome to Roxli Mail!</h1>
            <p style="margin: 0; font-size: 18px; opacity: 0.9;">Hi {user['firstName']}, your secure email journey begins now</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 40px 30px; color: #202124;">
            <!-- Getting Started -->
            <div style="margin-bottom: 40px;">
                <h2 style="color: #1a73e8; font-size: 24px; margin: 0 0 20px 0; display: flex; align-items: center;">
                    <span style="background: #e8f0fe; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 20px;">🚀</span>
                    Quick Start Guide
                </h2>
                <div style="background: #f8f9fa; padding: 25px; border-radius: 12px; border-left: 4px solid #1a73e8; color: #202124;">
                    <div style="display: flex; align-items: center; margin-bottom: 15px;">
                        <span style="background: #1a73e8; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; margin-right: 12px;">1</span>
                        <span><strong>Compose:</strong> Click the blue compose button to send your first email</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 15px;">
                        <span style="background: #1a73e8; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; margin-right: 12px;">2</span>
                        <span><strong>Organize:</strong> Use folders in the sidebar to keep emails organized</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 15px;">
                        <span style="background: #1a73e8; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; margin-right: 12px;">3</span>
                        <span><strong>Search:</strong> Find any email instantly with our powerful search</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <span style="background: #1a73e8; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; margin-right: 12px;">4</span>
                        <span><strong>Account:</strong> Manage settings at <a href="https://account.roxli.in" style="color: #1a73e8; text-decoration: none;">Account Dashboard</a></span>
                    </div>
                </div>
            </div>
            
            <!-- Security Features -->
            <div style="margin-bottom: 40px;">
                <h2 style="color: #34a853; font-size: 24px; margin: 0 0 20px 0; display: flex; align-items: center;">
                    <span style="background: #e8f5e8; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 20px;">🔒</span>
                    Security & Privacy
                </h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 8px;">🔐</div>
                        <div style="font-weight: 600; color: #34a853;">Encrypted</div>
                        <div style="font-size: 12px; color: #5f6368;">End-to-end encryption</div>
                    </div>
                    <div style="background: #e8f0fe; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 8px;">👥</div>
                        <div style="font-weight: 600; color: #1a73e8;">Multi-Account</div>
                        <div style="font-size: 12px; color: #5f6368;">Easy account switching</div>
                    </div>
                    <div style="background: #fef7e0; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 8px;">📱</div>
                        <div style="font-weight: 600; color: #f9ab00;">Device Control</div>
                        <div style="font-size: 12px; color: #5f6368;">Manage all devices</div>
                    </div>
                    <div style="background: #fce8e6; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 8px;">🔑</div>
                        <div style="font-weight: 600; color: #ea4335;">2FA Ready</div>
                        <div style="font-size: 12px; color: #5f6368;">Two-factor auth</div>
                    </div>
                </div>
            </div>
            
            <!-- Call to Action -->
            <div style="text-align: center; background: linear-gradient(135deg, #e8f0fe 0%, #f3e8ff 100%); padding: 30px; border-radius: 12px; margin-bottom: 30px;">
                <h3 style="color: #1a73e8; margin: 0 0 15px 0;">Ready to get started?</h3>
                <a href="https://mail.roxli.in" style="display: inline-block; background: #1a73e8; color: white; padding: 12px 30px; border-radius: 25px; text-decoration: none; font-weight: 600; margin: 0 10px 10px 0;">Open Roxli Mail</a>
                <a href="https://account.roxli.in" style="display: inline-block; background: transparent; color: #1a73e8; padding: 12px 30px; border: 2px solid #1a73e8; border-radius: 25px; text-decoration: none; font-weight: 600; margin: 0 10px 10px 0;">Account Settings</a>
            </div>
            
            <!-- Support -->
            <div style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0; color: #202124;">
                <p style="margin: 0 0 10px 0; color: #5f6368;">Need help? We're here for you!</p>
                <p style="margin: 0; font-size: 14px;">Reply to this email or visit our <a href="#" style="color: #1a73e8;">Help Center</a></p>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0; color: #202124;">
            <p style="margin: 0 0 10px 0; color: #1a73e8; font-weight: 600; font-size: 16px;">The Roxli Mail Team</p>
            <p style="margin: 0 0 15px 0; color: #5f6368; font-size: 14px;">Making email secure, simple, and beautiful</p>
            <div style="font-size: 12px; color: #9aa0a6; line-height: 1.5;">
                <p style="margin: 0;">This email was sent to {user['email']}</p>
                <p style="margin: 5px 0 0 0;">You received this because you created a Roxli Mail account</p>
            </div>
        </div>
    </div>
</body>
</html>''',
            'preview': f'Welcome to Roxli Mail, {user["firstName"]}! 🎉 Your secure email journey begins now. Quick start guide, security features, and everything you need to get started with your new email experience.',
            'message': f'Welcome to Roxli Mail, {user["firstName"]}! Your secure email experience starts here.',
            'timestamp': timestamp,
            'time': datetime.now().strftime('%I:%M %p'),
            'date': datetime.now().strftime('%B %d, %Y'),
            'read': False,
            'starred': True
        }
        
        print(f"Creating welcome email for user {user['id']} with email ID {email_id}")
        
        # Save welcome email to user's inbox
        result = mail_db.child(user['id']).child('inbox').child(email_id).set(welcome_email)
        print(f"Welcome email saved: {result}")
        
        # Send welcome notification
        try:
            send_notification_to_user(
                user['id'], 
                "Welcome to Roxli Mail! 🎉", 
                f"Hi {user['firstName']}, your secure email experience starts here!",
                {'email_id': email_id, 'type': 'welcome'}
            )
        except Exception as e:
            print(f"Failed to send welcome notification: {e}")
        
        return jsonify({'success': True, 'emailId': email_id})
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to send welcome email'}), 500

@app.route('/api/switch-account', methods=['POST'])
def switch_account():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    try:
        # Try to switch using main Roxli system
        import requests
        response = requests.post('https://auth.roxli.in/api/switch-account', 
                               json={'email': email}, 
                               timeout=5,
                               cookies=request.cookies)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('token'):
                # Set the new token
                resp = jsonify({'success': True})
                resp.set_cookie('roxli_token', data['token'], httponly=False, secure=False, samesite='Lax', path='/')
                return resp
        
        return jsonify({'error': 'Switch failed'}), 400
    except Exception as e:
        print(f"Error switching account: {e}")
        return jsonify({'error': 'Switch failed'}), 500

@app.route('/api/subscribe-notifications', methods=['POST'])
def subscribe_notifications():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    token = data.get('token')
    notification_type = data.get('type', 'browser')
    device_id = data.get('deviceId', 'unknown')
    user_agent = data.get('userAgent', request.headers.get('User-Agent', ''))
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    try:
        mail_db = db.reference('notifications', app=mail_app)
        
        # Store device-specific notification settings
        device_settings = {
            'notifications_enabled': True,
            'token': token,
            'type': notification_type,
            'device_id': device_id,
            'user_agent': user_agent[:200],
            'subscribed_at': datetime.now().timestamp(),
            'ip_address': request.remote_addr,
            'last_active': datetime.now().timestamp()
        }
        
        # Store per device to support multiple devices
        mail_db.child('user_devices').child(user['id']).child(device_id).set(device_settings)
        
        # Test notification
        if notification_type == 'fcm':
            try:
                send_fcm_notification(
                    token,
                    "Roxli Mail Notifications Enabled",
                    "You'll now receive push notifications for new emails!",
                    {'type': 'test'}
                )
            except Exception as e:
                print(f"Failed to send test FCM notification: {e}")
        
        return jsonify({'success': True, 'message': 'Notifications enabled successfully'})
    except Exception as e:
        print(f"Error subscribing to notifications: {e}")
        return jsonify({'error': 'Failed to subscribe'}), 500

@app.route('/api/notifications')
def get_notifications():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mail_db = db.reference('notifications', app=mail_app)
        user_notifications = mail_db.child('user_notifications').child(user['id']).get() or {}
        
        notifications = []
        for notif_id, notif_data in user_notifications.items():
            if not notif_data.get('read', False):
                notifications.append({
                    'id': notif_id,
                    'title': notif_data.get('title', ''),
                    'body': notif_data.get('body', ''),
                    'data': notif_data.get('data', {}),
                    'timestamp': notif_data.get('timestamp', 0)
                })
        
        # Sort by timestamp (newest first)
        notifications.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return jsonify({'notifications': notifications})
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify({'notifications': []})

@app.route('/api/mark-notification-read', methods=['POST'])
def mark_notification_read():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    notification_id = data.get('notificationId')
    
    try:
        mail_db = db.reference('notifications', app=mail_app)
        mail_db.child('user_notifications').child(user['id']).child(notification_id).update({'read': True})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Failed to mark notification as read'}), 500

def send_fcm_notification(token, title, body, data=None):
    """Send FCM push notification"""
    try:
        if not mail_app:
            print("Firebase app not initialized")
            return False
        
        # Ensure data values are strings
        string_data = {}
        if data:
            for key, value in data.items():
                string_data[key] = str(value) if value is not None else ''
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=string_data,
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    title=title,
                    body=body,
                    icon='logo',
                    color='#1a73e8',
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            ),
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon='/static/images/logo.png',
                    badge='/static/images/logo.png',
                    tag='roxli-mail',
                    require_interaction=True
                ),
                fcm_options=messaging.WebpushFCMOptions(
                    link='https://mail.roxli.in'
                )
            )
        )
        
        response = messaging.send(message, app=mail_app)
        print(f"FCM notification sent successfully: {response}")
        return True
        
    except Exception as e:
        print(f"Error sending FCM notification: {e}")
        # If token is invalid, return False to trigger cleanup
        if 'not-registered' in str(e) or 'invalid-registration-token' in str(e):
            return False
        return False

def send_notification_to_user(user_id, title, body, data=None):
    """Send notification to user via FCM and store in database"""
    try:
        # Store notification in database for client-side polling
        mail_db = db.reference('notifications', app=mail_app)
        notification_id = str(uuid.uuid4())
        
        notification_data = {
            'id': notification_id,
            'user_id': user_id,
            'title': title,
            'body': body,
            'data': data or {},
            'timestamp': datetime.now().timestamp(),
            'read': False
        }
        
        # Store notification
        mail_db.child('user_notifications').child(user_id).child(notification_id).set(notification_data)
        
        # Send to all user devices
        try:
            user_devices = mail_db.child('user_devices').child(user_id).get() or {}
            notification_sent = False
            
            for device_id, device_settings in user_devices.items():
                if device_settings.get('notifications_enabled') and device_settings.get('token'):
                    token = device_settings['token']
                    notification_type = device_settings.get('type', 'browser')
                    
                    if notification_type == 'fcm':
                        success = send_fcm_notification(token, title, body, data)
                        if success:
                            print(f"FCM notification sent to device {device_id} for user {user_id}")
                            notification_sent = True
                        else:
                            print(f"Failed to send FCM to device {device_id}, removing invalid token")
                            # Remove invalid token
                            mail_db.child('user_devices').child(user_id).child(device_id).delete()
                    elif notification_type == 'browser':
                        # For browser notifications, we'll handle them client-side
                        print(f"Browser notification queued for device {device_id}")
                        notification_sent = True
            
            if not notification_sent:
                print(f"No active devices found for user {user_id}")
                
        except Exception as e:
            print(f"Error sending push notifications: {e}")
        
        print(f"Notification stored for user {user_id}: {title}")
        return True
        
    except Exception as e:
        print(f"Error storing notification: {e}")
        return False

@app.route('/api/cleanup-emails', methods=['POST'])
def cleanup_emails():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mail_db = db.reference('emails', app=mail_app)
        user_emails = mail_db.child(user['id']).child('inbox').get() or {}
        
        cleaned_count = 0
        for email_id, email_data in user_emails.items():
            needs_update = False
            update_data = {}
            
            # Clean all text fields
            for field in ['subject', 'preview', 'body', 'message']:
                original = email_data.get(field, '')
                if original and ('<<<<<<< HEAD' in original or '=======' in original or '>>>>>>> ' in original):
                    cleaned = clean_merge_conflicts(original)
                    if cleaned != original:
                        update_data[field] = cleaned
                        needs_update = True
            
            if needs_update:
                mail_db.child(user['id']).child('inbox').child(email_id).update(update_data)
                cleaned_count += 1
                print(f"Cleaned email {email_id}: {list(update_data.keys())}")
        
        return jsonify({'success': True, 'cleaned': cleaned_count})
    except Exception as e:
        print(f"Error cleaning emails: {e}")
        return jsonify({'error': 'Failed to clean emails'}), 500

@app.route('/api/available-accounts')
def get_available_accounts():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        emails = request.args.getlist('emails')
        accounts = []
        
        for email in emails:
            if email != user['email']:
                # Mock account data - in real implementation, fetch from auth service
                name_parts = email.split('@')[0].split('.')
                first_name = name_parts[0].capitalize() if name_parts else 'User'
                last_name = name_parts[1].capitalize() if len(name_parts) > 1 else ''
                
                accounts.append({
                    'email': email,
                    'firstName': first_name,
                    'lastName': last_name,
                    'avatar': f'https://ui-avatars.com/api/?name={first_name}+{last_name}&background=667eea&color=fff&size=32'
                })
        
        return jsonify({'accounts': accounts})
    except Exception as e:
        print(f"Error fetching available accounts: {e}")
        return jsonify({'accounts': []})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(debug=False, host='0.0.0.0', port=port)