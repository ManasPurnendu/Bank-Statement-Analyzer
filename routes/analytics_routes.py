from flask import Blueprint, jsonify, request, session
from utils.decorators import login_required
from services.analytics import calculate_analytics, get_date_range_for_type

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics', methods=['GET'])
@login_required
def get_analytics_data():
    try:
        user_id = session.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            range_type = request.args.get('range', 'all')
            start_date, end_date = get_date_range_for_type(range_type, user_id=user_id)
        
        analytics = calculate_analytics(start_date, end_date, user_id=user_id)
        return jsonify({
            "success": True,
            "analytics": analytics
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading analytics data: {str(e)}"
        }), 500
