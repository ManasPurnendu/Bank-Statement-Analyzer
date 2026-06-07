from flask import Flask, render_template, redirect, url_for
import os
from database.db import init_db
from routes.upload_routes import upload_bp
from routes.dashboard_routes import dashboard_bp
from routes.transaction_routes import transaction_bp
from routes.analytics_routes import analytics_bp
from routes.forecast_routes import forecast_bp
from routes.report_routes import report_bp

app = Flask(__name__)
app.secret_key = 'bank_statement_analyzer_secret_key'

# Configuration Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
REPORT_FOLDER = os.path.join(BASE_DIR, 'generated_reports')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORT_FOLDER'] = REPORT_FOLDER

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

# --- HTML Page Render Routes ---

@app.route('/')
def landing_page():
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/transactions')
def transactions_page():
    return render_template('transactions.html')

@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

@app.route('/forecasts')
@app.route('/forecast')
def forecast_page():
    return render_template('forecast.html')

@app.route('/reports')
@app.route('/report')
def reports_page():
    return render_template('reports.html')

if __name__ == '__main__':
    # Run the server on port 5001 in debug mode
    app.run(host='0.0.0.0', port=5001, debug=True)
