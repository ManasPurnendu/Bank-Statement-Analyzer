from flask import Flask, render_template, redirect, url_for, jsonify, session
import os
import secrets
import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

from database.db import init_db
from routes.upload_routes import upload_bp
from routes.dashboard_routes import dashboard_bp
from routes.transaction_routes import transaction_bp
from routes.analytics_routes import analytics_bp
from routes.forecast_routes import forecast_bp
from routes.report_routes import report_bp
from routes.auth_routes import auth_bp
from utils.decorators import login_required, admin_required

# --- Load Environment Variables ---
load_dotenv()

app = Flask(__name__)

# --- Setup Logging (ISS-003) ---
log_formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s %(pathname)s %(lineno)d')
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
file_handler = RotatingFileHandler(log_file, maxBytes=1024000, backupCount=10)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Bank Statement Analyser startup')

# --- Security: Flask Secret Key & CSRF (ISS-005) ---
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError("FATAL: SECRET_KEY environment variable is not set. Refusing to start in production.")
app.secret_key = secret_key
csrf = CSRFProtect(app)

# Session configuration
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=8)  # 8 hour session timeout

# Configuration Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_FOLDER = os.path.join(BASE_DIR, 'generated_reports')

app.config['REPORT_FOLDER'] = REPORT_FOLDER

# --- Security: File Upload Size Limit (S-03) ---
# Prevent Denial of Service (DoS) attacks via memory or disk exhaustion.
# 16 MB is a sensible limit for bank statements (PDFs or Excel spreadsheets).
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure folders exist
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Initialize Database on Startup
init_db()

# Register Blueprints with /api/v1 Prefix
app.register_blueprint(upload_bp, url_prefix='/api/v1')
app.register_blueprint(dashboard_bp, url_prefix='/api/v1')
app.register_blueprint(transaction_bp, url_prefix='/api/v1')
app.register_blueprint(analytics_bp, url_prefix='/api/v1')
app.register_blueprint(forecast_bp, url_prefix='/api/v1')
app.register_blueprint(report_bp, url_prefix='/api/v1')
app.register_blueprint(auth_bp, url_prefix='/auth')

# --- Health Check Route ---
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "version": "1.0.0"})

# --- HTML Page Render Routes ---

@app.route('/')
def landing_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/transactions')
@login_required
def transactions_page():
    return render_template('transactions.html')

@app.route('/analytics')
@login_required
def analytics_page():
    return render_template('analytics.html')

@app.route('/forecasts')
@app.route('/forecast')
@login_required
def forecast_page():
    return render_template('forecast.html')

@app.route('/reports')
@app.route('/report')
@login_required
def reports_page():
    return render_template('reports.html')

@app.route('/admin/users')
@login_required
@admin_required
def admin_users_page():
    return render_template('admin_users.html')


# --- Error Handlers ---
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "success": False,
        "message": "Maximum supported upload size is 16 MB."
    }), 413

if __name__ == '__main__':
    # During local development without Docker, use the built-in server.
    # In production (via Docker), Gunicorn will import 'app' and serve it directly.
    app.run(host='0.0.0.0', port=5001, debug=True)
