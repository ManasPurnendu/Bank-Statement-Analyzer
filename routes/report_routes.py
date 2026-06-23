from flask import Blueprint, request, jsonify, current_app, send_from_directory, session
from utils.decorators import login_required
import os
import time
from datetime import datetime
from services.report_generator import generate_pdf_report
from services.analytics import calculate_analytics, get_date_range_for_type

report_bp = Blueprint('report', __name__)

def get_friendly_info(filename):
    """
    Parses a report file name to extract report details for UI rendering.
    Example: "Financial_Summary_-_Jan_to_May_2025_1717731234.pdf"
    """
    base = filename.rsplit('.', 1)[0]
    # Remove timestamp suffix if present
    if '_' in base:
        parts = base.split('_')
        timestamp_str = parts[-1]
        if timestamp_str.isdigit():
            base = "_".join(parts[:-1])
            
    # Replace underscores with spaces for readability
    friendly_name = base.replace('_', ' ')
    
    # Deduce Type
    rpt_type = "Custom"
    if "Financial Summary" in friendly_name:
        rpt_type = "Summary"
    elif "Detailed Transactions" in friendly_name:
        rpt_type = "Detailed"
    elif "Spending Analytics" in friendly_name:
        rpt_type = "Analytics"
        
    return friendly_name, rpt_type

@report_bp.route('/report/generate', methods=['POST'])
@login_required
def generate_report():
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        report_type = data.get('report_type', 'Summary') # 'Summary', 'Detailed', 'Analytics', 'Custom'
        date_range = data.get('date_range', 'all')
        sections = data.get('sections', None)
        
        # Resolve dates
        start_date, end_date = get_date_range_for_type(date_range, user_id=user_id)
        
        # Build period string and file suffix
        if start_date and end_date:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            period_str = f"{s_dt.strftime('%d %b %Y')} - {e_dt.strftime('%d %b %Y')}"
            range_suffix = f"{start_date}_to_{end_date}"
        else:
            period_str = "All Time"
            range_suffix = "All_Time"
            
        # Build file name
        timestamp = int(time.time())
        name_prefix = "Financial_Summary"
        if report_type == "Detailed":
            name_prefix = "Detailed_Transactions"
        elif report_type == "Analytics":
            name_prefix = "Spending_Analytics"
        elif report_type == "Custom":
            name_prefix = "Custom_Report"
            
        filename = f"{name_prefix}_-_{range_suffix}_{timestamp}.pdf"
        
        report_dir = os.path.join(current_app.config['REPORT_FOLDER'], str(user_id))
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        dest_path = os.path.join(report_dir, filename)
        
        # Call generator
        generate_pdf_report(dest_path, report_type, period_str, sections, start_date, end_date, user_id=user_id)
        
        return jsonify({
            "success": True,
            "message": "Report generated successfully.",
            "filename": filename
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error generating report: {str(e)}"
        }), 500

@report_bp.route('/reports', methods=['GET'])
@login_required
def list_reports():
    try:
        user_id = session.get('user_id')
        report_dir = os.path.join(current_app.config['REPORT_FOLDER'], str(user_id))
        reports_list = []
        
        if os.path.exists(report_dir):
            for filename in os.listdir(report_dir):
                if filename.endswith('.pdf'):
                    path = os.path.join(report_dir, filename)
                    stat = os.stat(path)
                    
                    friendly_name, rpt_type = get_friendly_info(filename)
                    file_size_mb = stat.st_size / (1024 * 1024)
                    generated_time = datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y, %I:%M %p")
                    
                    # Parse start_date and end_date from filename
                    display_range = "All Time"
                    try:
                        if "_-_" in filename:
                            range_part = filename.split("_-_")[1]
                            range_part = range_part.rsplit("_", 1)[0]
                            if "_to_" in range_part:
                                s_str, e_str = range_part.split("_to_")
                                s_dt = datetime.strptime(s_str, "%Y-%m-%d")
                                e_dt = datetime.strptime(e_str, "%Y-%m-%d")
                                display_range = f"{s_dt.strftime('%d %b %Y')} - {e_dt.strftime('%d %b %Y')}"
                            elif range_part == "All_Time":
                                display_range = "All Time"
                            else:
                                display_range = range_part.replace("_", " ")
                    except Exception:
                        pass
                        
                    reports_list.append({
                        "name": friendly_name,
                        "filename": filename,
                        "type": rpt_type,
                        "date_range": display_range,
                        "generated_on": generated_time,
                        "file_size": f"{file_size_mb:.2f} MB"
                    })
                    
        # Sort by generated_on descending (we can sort by filename timestamp or modified time)
        reports_list.sort(key=lambda x: x["filename"].split('_')[-1] if '_' in x["filename"] else x["generated_on"], reverse=True)
        return jsonify({
            "success": True,
            "reports": reports_list
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error listing reports: {str(e)}"
        }), 500

@report_bp.route('/report/download/<filename>', methods=['GET'])
@login_required
def download_report(filename):
    user_id = session.get('user_id')
    report_dir = os.path.join(current_app.config['REPORT_FOLDER'], str(user_id))
    return send_from_directory(report_dir, filename, as_attachment=True)

@report_bp.route('/report/view/<filename>', methods=['GET'])
@login_required
def view_report(filename):
    user_id = session.get('user_id')
    report_dir = os.path.join(current_app.config['REPORT_FOLDER'], str(user_id))
    return send_from_directory(report_dir, filename, as_attachment=False)

@report_bp.route('/report/<filename>', methods=['DELETE'])
@login_required
def delete_report(filename):
    try:
        user_id = session.get('user_id')
        report_dir = os.path.join(current_app.config['REPORT_FOLDER'], str(user_id))
        path = os.path.join(report_dir, filename)
        if os.path.exists(path):
            os.remove(path)
            return jsonify({"success": True, "message": "Report deleted successfully."})
        else:
            return jsonify({"success": False, "message": "Report not found."}), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error deleting report: {str(e)}"
        }), 500
