from flask import Blueprint, jsonify, request
from services.analytics import calculate_analytics, get_date_range_for_type

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics', methods=['GET'])
def get_analytics_data():
    try:
        range_type = request.args.get('range', 'all')
        start_date, end_date = get_date_range_for_type(range_type)
        
        analytics = calculate_analytics(start_date, end_date)
        return jsonify({
            "success": True,
            "analytics": analytics
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading analytics data: {str(e)}"
        }), 500
