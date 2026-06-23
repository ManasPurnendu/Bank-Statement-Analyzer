from flask import Blueprint, request, jsonify, session
from utils.decorators import login_required
from services.forecast import generate_forecast
from services.analytics import get_date_range_for_type

forecast_bp = Blueprint('forecast', __name__)

@forecast_bp.route('/forecast', methods=['GET'])
@login_required
def get_forecast():
    try:
        user_id = session.get('user_id')
        horizon = request.args.get('horizon', 3)
        try:
            horizon = int(horizon)
        except ValueError:
            horizon = 3
            
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            range_type = request.args.get('range', 'all')
            start_date, end_date = get_date_range_for_type(range_type, user_id=user_id)
            
        data = generate_forecast(horizon=horizon, start_date=start_date, end_date=end_date, user_id=user_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error generating forecast: {str(e)}"
        }), 500

@forecast_bp.route('/forecast/simulate', methods=['POST'])
@login_required
def simulate_scenario():
    try:
        user_id = session.get('user_id')
        req_data = request.json or {}
        category = req_data.get('category')
        reduction = req_data.get('reduction', 0.0)
        horizon = req_data.get('horizon', 3)
        try:
            horizon = int(horizon)
        except ValueError:
            horizon = 3
        
        try:
            reduction = float(reduction)
        except ValueError:
            return jsonify({"success": False, "message": "Reduction must be a numeric value."}), 400
            
        start_date = req_data.get('start_date') or request.args.get('start_date')
        end_date = req_data.get('end_date') or request.args.get('end_date')
        if not start_date or not end_date:
            range_type = req_data.get('range') or request.args.get('range', 'all')
            start_date, end_date = get_date_range_for_type(range_type, user_id=user_id)
            
        data = generate_forecast(category, reduction, horizon=horizon, start_date=start_date, end_date=end_date, user_id=user_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error simulating scenario: {str(e)}"
        }), 500
