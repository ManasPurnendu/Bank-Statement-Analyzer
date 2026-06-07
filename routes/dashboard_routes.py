from flask import Blueprint, jsonify, request
from services.analytics import calculate_analytics, get_date_range_for_type
from services.insights import generate_insights

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        range_type = request.args.get('range', 'all')
        start_date, end_date = get_date_range_for_type(range_type)
        
        analytics = calculate_analytics(start_date, end_date)
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
