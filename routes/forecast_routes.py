from flask import Blueprint, request, jsonify
from services.forecast import generate_forecast

forecast_bp = Blueprint('forecast', __name__)

@forecast_bp.route('/forecast', methods=['GET'])
def get_forecast():
    try:
        horizon = request.args.get('horizon', 3)
        try:
            horizon = int(horizon)
        except ValueError:
            horizon = 3
            
        data = generate_forecast(horizon=horizon)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error generating forecast: {str(e)}"
        }), 500

@forecast_bp.route('/forecast/simulate', methods=['POST'])
def simulate_scenario():
    try:
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
            
        data = generate_forecast(category, reduction, horizon=horizon)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error simulating scenario: {str(e)}"
        }), 500
