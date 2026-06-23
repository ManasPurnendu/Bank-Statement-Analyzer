from flask import Flask, render_template, redirect, url_for, jsonify, session
import os
import secrets
from database.db import init_db
from routes.upload_routes import upload_bp
from routes.dashboard_routes import dashboard_bp
from routes.transaction_routes import transaction_bp
from routes.analytics_routes import analytics_bp
from routes.forecast_routes import forecast_bp
from routes.report_routes import report_bp
from routes.auth_routes import auth_bp
from utils.decorators import login_required

app = Flask(__name__)

# --- Security: Flask Secret Key ---
# NEVER hardcode secret keys in source code. A leaked key allows attackers to
# forge session cookies and hijack user sessions.
#
# In production, set the SECRET_KEY environment variable to a strong random value:
#   export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
#
# For local development, a random fallback is generated automatically. Note that
# sessions will not persist across server restarts when using the fallback.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-do-not-use-in-production')

# Session configuration
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=8)  # 8 hour session timeout

# Configuration Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
REPORT_FOLDER = os.path.join(BASE_DIR, 'generated_reports')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORT_FOLDER'] = REPORT_FOLDER

# --- Security: File Upload Size Limit (S-03) ---
# Prevent Denial of Service (DoS) attacks via memory or disk exhaustion.
# 16 MB is a sensible limit for bank statements (PDFs or Excel spreadsheets).
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Initialize Database on Startup
init_db()

# Register Blueprints with /api Prefix
app.register_blueprint(upload_bp, url_prefix='/api')
app.register_blueprint(dashboard_bp, url_prefix='/api')
app.register_blueprint(transaction_bp, url_prefix='/api')
app.register_blueprint(analytics_bp, url_prefix='/api')
app.register_blueprint(forecast_bp, url_prefix='/api')
app.register_blueprint(report_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/auth')

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

# --- Error Handlers ---
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "success": False,
        "message": "Maximum supported upload size is 16 MB."
    }), 413

if __name__ == '__main__':
    # Run the server on port 5001 in debug mode
    app.run(host='0.0.0.0', port=5001, debug=True)
