from flask import Blueprint, request, jsonify, current_app, session
from utils.decorators import login_required
import os
import hashlib
from werkzeug.utils import secure_filename
from parsers.unified_parser import parse_statement
from database.models import check_duplicate_statement, add_statement, add_transactions_bulk, delete_statement, get_all_statements

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'xls', 'xlsx', 'csv', 'json'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    user_id = session.get('user_id')
    # Check if this is a request to seed demo data
    if request.form.get('demo') == 'true':
        try:
            demo_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'sample_statement_jan_may_2025.xlsx')
            if not os.path.exists(demo_file):
                from tests.generate_sample_data import create_sample_excel
                create_sample_excel()
            
            parsed_data = parse_statement(demo_file, demo_file)
            metadata = parsed_data["metadata"]
            transactions = parsed_data["transactions"]
            
            # Calculate file hash for demo file
            with open(demo_file, 'rb') as f:
                demo_hash = hashlib.sha256(f.read()).hexdigest()

            # Delete if duplicate exists (to ensure a clean reload)
            dup_id = check_duplicate_statement(
                metadata["account_number"], 
                metadata["start_date"], 
                metadata["end_date"], 
                metadata["transaction_count"],
                file_hash=demo_hash,
                user_id=user_id
            )
            if dup_id:
                delete_statement(dup_id, user_id=user_id)
                
            stmt_id = add_statement(
                metadata["file_name"], metadata["file_type"], metadata["account_holder"],
                metadata["account_number"], metadata["bank_name"], metadata["statement_month"],
                metadata["start_date"], metadata["end_date"], metadata["transaction_count"],
                metadata["opening_balance"], metadata["closing_balance"],
                file_hash=demo_hash, user_id=user_id
            )
            
            for t in transactions:
                t["statement_id"] = stmt_id
                t["user_id"] = user_id
                
            add_transactions_bulk(transactions)
            active_statements = len(get_all_statements())
            
            return jsonify({
                "success": True,
                "transactions": len(transactions),
                "statements": active_statements
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Error seeding demo data: {str(e)}"}), 500

    if 'files' not in request.files:
        return jsonify({"success": False, "message": "No files provided in request."}), 400
        
    files = request.files.getlist('files')
    password = request.form.get('password', None)
    action = request.form.get('action', None) # 'replace', 'skip'
    
    if not files or len(files) == 0 or files[0].filename == '':
        return jsonify({"success": False, "message": "No files selected."}), 400
        
    uploaded_statements = []
    total_transactions_parsed = 0
    
    for file in files:
        if not file or not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "message": f"Unsupported file type: {file.filename}. Supported formats are PDF, XLS, XLSX."
            }), 400
            
        # Save file temporarily in uploads directory
        filename = secure_filename(file.filename)
        upload_dir = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        # Calculate file hash
        file.seek(0)
        file_bytes = file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file.seek(0) # Reset stream pointer

        temp_path = os.path.join(upload_dir, filename)
        file.save(temp_path)
        stmt_id = None
        try:
            # Parse statement through the unified parser
            try:
                parsed_data = parse_statement(temp_path, filename, password=password)
            except ValueError as ve:
                err = str(ve)
                if err == "PasswordRequired":
                    return jsonify({
                        "success": False,
                        "error": "PasswordRequired",
                        "message": "This file is password-protected. Please enter the password."
                    }), 401
                elif err == "IncorrectPassword":
                    return jsonify({
                        "success": False,
                        "error": "IncorrectPassword",
                        "message": "Incorrect password. The password does not match the uploaded file."
                    }), 401
                else:
                    raise ve
                
            metadata = parsed_data["metadata"]
            transactions = parsed_data["transactions"]
            
            # Check for duplicates
            dup_id = check_duplicate_statement(
                metadata["account_number"], 
                metadata["start_date"], 
                metadata["end_date"], 
                metadata["transaction_count"],
                file_hash=file_hash,
                user_id=user_id
            )
            
            if dup_id:
                if action == 'replace':
                    delete_statement(dup_id, user_id=user_id)
                elif action == 'skip':
                    # Clean up file and proceed to next file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue
                else:
                    # Return prompt for decision
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return jsonify({
                        "success": False,
                        "error": "DuplicateStatement",
                        "message": f"Statement '{filename}' already exists.",
                        "details": {
                            "file_name": filename,
                            "account_number": metadata["account_number"],
                            "period": f"{metadata['start_date']} to {metadata['end_date']}",
                            "count": metadata["transaction_count"]
                        }
                    }), 409
                    
            # Insert Statement Metadata
            stmt_id = add_statement(
                metadata["file_name"], metadata["file_type"], metadata["account_holder"],
                metadata["account_number"], metadata["bank_name"], metadata["statement_month"],
                metadata["start_date"], metadata["end_date"], metadata["transaction_count"],
                metadata["opening_balance"], metadata["closing_balance"],
                file_hash=file_hash, user_id=user_id
            )
            
            # Link transactions to statement ID and insert bulk
            for t in transactions:
                t["statement_id"] = stmt_id
                t["user_id"] = user_id
                
            add_transactions_bulk(transactions)
            
            total_transactions_parsed += len(transactions)
            uploaded_statements.append(stmt_id)
            
        except Exception as e:
            if stmt_id is not None:
                try:
                    delete_statement(stmt_id, user_id=user_id)
                except Exception:
                    pass
            # Cleanup and return error
            return jsonify({
                "success": False, 
                "message": f"Error parsing '{filename}': {str(e)}"
            }), 500
        finally:
            # Delete uploaded file immediately after parsing
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    # Return count of active statements
    active_statements = len(get_all_statements())
    
    return jsonify({
        "success": True,
        "transactions": total_transactions_parsed,
        "statements": active_statements
    })

@upload_bp.route('/statements', methods=['GET'])
@login_required
def list_statements():
    try:
        user_id = session.get('user_id')
        statements = get_all_statements(user_id=user_id)
        return jsonify({
            "success": True,
            "statements": statements
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading statements: {str(e)}"
        }), 500

@upload_bp.route('/statement/<int:statement_id>', methods=['DELETE'])
@login_required
def delete_statement_endpoint(statement_id):
    try:
        user_id = session.get('user_id')
        delete_statement(statement_id, user_id=user_id)
        return jsonify({
            "success": True,
            "message": "Statement and all associated transactions removed successfully."
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error deleting statement: {str(e)}"
        }), 500
