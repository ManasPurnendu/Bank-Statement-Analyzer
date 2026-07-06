from flask import Blueprint, jsonify, request, session
from services.analytics import calculate_analytics, get_date_range_for_type
from services.insights import generate_insights
from services.engines.income_intelligence import IncomeIntelligenceOrchestrator
from database.db import get_db_connection
from database.models import add_intelligence_report, get_latest_intelligence_report
from utils.decorators import login_required, admin_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard_data():
    try:
        user_id = session.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            range_type = request.args.get('range', 'all')
            start_date, end_date = get_date_range_for_type(range_type, user_id=user_id)
        
        analytics = calculate_analytics(start_date, end_date, user_id=user_id)
        insights = generate_insights(analytics)
        
        return jsonify({
            "success": True,
            "analytics": analytics,
            "insights": insights
        })
    except Exception as e:
        print("DASHBOARD ERROR:", str(e))

        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": f"Error loading dashboard: {str(e)}"
        }), 500

# --- Admin Routes for Intelligence V2.3 ---

@dashboard_bp.route('/admin/api/users', methods=['GET'])
@login_required
@admin_required
def get_all_users():
    conn = get_db_connection()
    conn.row_factory = __import__('sqlite3').Row
    cursor = conn.cursor()
    
    # Fetch all users
    cursor.execute('''
        SELECT u.user_id, u.email, u.role
        FROM users u
        ORDER BY u.user_id DESC
    ''')
    users = []
    
    for row in cursor.fetchall():
        user_dict = dict(row)
        
        # Fetch statements for this user
        cursor.execute('''
            SELECT s.statement_id, s.file_name, s.upload_date,
                   (SELECT income_classification FROM income_intelligence_reports r WHERE r.statement_id = s.statement_id ORDER BY created_at DESC LIMIT 1) as income_classification
            FROM statements s
            WHERE s.user_id = ?
            ORDER BY s.upload_date DESC
        ''', (user_dict['user_id'],))
        
        statements = [dict(s_row) for s_row in cursor.fetchall()]
        user_dict['statements'] = statements
        user_dict['statement_count'] = len(statements)
        
        # Determine aggregate status just for display if needed
        user_dict['income_classification'] = None
        if statements:
            # Maybe show the latest statement's status as the top-level status
            user_dict['income_classification'] = statements[0]['income_classification']
            
        users.append(user_dict)
        
    conn.close()
    
    return jsonify({"success": True, "users": users})

@dashboard_bp.route('/admin/intelligence/generate/<int:statement_id>', methods=['POST'])
@login_required
@admin_required
def generate_intelligence_report(statement_id):
    try:
        conn = get_db_connection()
        conn.row_factory = __import__('sqlite3').Row
        cursor = conn.cursor()
        
        # Get all transactions for statement
        cursor.execute('SELECT * FROM transactions WHERE statement_id = ? ORDER BY transaction_date ASC', (statement_id,))
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Get user_id for the statement
        cursor.execute('SELECT user_id FROM statements WHERE statement_id = ?', (statement_id,))
        statement_row = cursor.fetchone()
        user_id = statement_row['user_id'] if statement_row and 'user_id' in statement_row.keys() else None
        # Actually user_id is in transactions, but in case there are no transactions, we can get it from statement.
        # Wait, if statement doesn't have user_id, we can get it from transaction.
        if not user_id and transactions:
            user_id = transactions[0].get('user_id')
            
        if not transactions:
            conn.close()
            return jsonify({"success": False, "message": "No transactions found for this statement."}), 404
            
        conn.close()
        
        # Run the V2.3 Master Orchestrator
        report_data = IncomeIntelligenceOrchestrator.generate_report(transactions)
        report_data['user_id'] = user_id
        report_data['statement_id'] = statement_id
        
        # Save to DB
        report_id = add_intelligence_report(report_data)
        
        return jsonify({
            "success": True,
            "message": "Intelligence Report Generated Successfully",
            "report_id": report_id,
            "income_classification": report_data['income_classification']
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@dashboard_bp.route('/admin/intelligence/report/<int:statement_id>', methods=['GET'])
@login_required
@admin_required
def get_intelligence_report(statement_id):
    report = get_latest_intelligence_report(statement_id=statement_id)
    if not report:
        return jsonify({"success": False, "message": "No report found."}), 404
        
    return jsonify({"success": True, "report": report})

