from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.models import create_user, get_user_by_email, record_failed_login, reset_failed_attempts, set_user_role
from utils.decorators import login_required, admin_required
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        return render_template('login.html')
        
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template('login.html')
        
    user = get_user_by_email(email)
    if not user:
        flash("Invalid credentials.", "danger")
        return render_template('login.html')
        
    if user['locked_until']:
        if datetime.utcnow() < datetime.fromisoformat(user['locked_until']):
            flash("Account is locked due to too many failed attempts. Try again later.", "danger")
            return render_template('login.html')
            
    if not check_password_hash(user['password_hash'], password):
        record_failed_login(user['user_id'])
        flash("Invalid credentials.", "danger")
        return render_template('login.html')
        
    reset_failed_attempts(user['user_id'])
    session.permanent = True
    session['user_id'] = user['user_id']
    session['role'] = user['role']
    session['email'] = user['email']
    
    return redirect(url_for('dashboard_page'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'GET':
        return render_template('register.html')
        
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template('register.html')
        
    if not PASSWORD_REGEX.match(password):
        flash("Password must be at least 8 characters and contain uppercase, lowercase, number, and special character.", "danger")
        return render_template('register.html')
        
    existing = get_user_by_email(email)
    if existing:
        flash("Email already registered.", "danger")
        return render_template('register.html')
        
    user_id = create_user(email, password, role='user')
    if user_id:
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('auth.login_page'))
    else:
        flash("Registration failed. Please try again.", "danger")
        return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))
