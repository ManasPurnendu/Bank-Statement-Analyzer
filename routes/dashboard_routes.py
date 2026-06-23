from flask import Blueprint, jsonify, request, session
from services.analytics import calculate_analytics, get_date_range_for_type
from services.insights import generate_insights
from utils.decorators import login_required

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
