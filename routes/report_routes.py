from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
import time
from datetime import datetime
from services.report_generator import generate_pdf_report
from services.analytics import calculate_analytics

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
def generate_report():
    try:
        data = request.json or {}
        report_type = data.get('report_type', 'Summary') # 'Summary', 'Detailed', 'Analytics', 'Custom'
        date_range = data.get('date_range', 'Jan to May 2025')
        sections = data.get('sections', None)
        
        # Build file name
        timestamp = int(time.time())
        name_prefix = "Financial_Summary"
        if report_type == "Detailed":
            name_prefix = "Detailed_Transactions"
        elif report_type == "Analytics":
            name_prefix = "Spending_Analytics"
        elif report_type == "Custom":
            name_prefix = "Custom_Report"
            
        filename = f"{name_prefix}_-_Jan_to_May_2025_{timestamp}.pdf"
        
        report_dir = current_app.config['REPORT_FOLDER']
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        dest_path = os.path.join(report_dir, filename)
        
        # Call generator
        generate_pdf_report(dest_path, report_type, date_range, sections)
        
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
def list_reports():
    try:
        report_dir = current_app.config['REPORT_FOLDER']
        reports_list = []
        
        if os.path.exists(report_dir):
            for filename in os.listdir(report_dir):
                if filename.endswith('.pdf'):
                    path = os.path.join(report_dir, filename)
                    stat = os.stat(path)
                    
                    friendly_name, rpt_type = get_friendly_info(filename)
                    file_size_mb = stat.st_size / (1024 * 1024)
                    generated_time = datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y, %I:%M %p")
                    
                    reports_list.append({
                        "name": friendly_name,
                        "filename": filename,
                        "type": rpt_type,
                        "date_range": "01 Jan 2025 - 31 May 2025",
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
def download_report(filename):
    report_dir = current_app.config['REPORT_FOLDER']
    return send_from_directory(report_dir, filename, as_attachment=True)

@report_bp.route('/report/view/<filename>', methods=['GET'])
def view_report(filename):
    report_dir = current_app.config['REPORT_FOLDER']
    return send_from_directory(report_dir, filename, as_attachment=False)

@report_bp.route('/report/<filename>', methods=['DELETE'])
def delete_report(filename):
    try:
        report_dir = current_app.config['REPORT_FOLDER']
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
