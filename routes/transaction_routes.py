from flask import Blueprint, request, jsonify, session
from utils.decorators import login_required
from database.models import get_transactions, get_transactions_count, get_all_categories, update_transaction_category, update_merchant_category_rules
from database.db import get_db_connection
import math

transaction_bp = Blueprint('transaction', __name__)

@transaction_bp.route('/transactions', methods=['GET'])
@login_required
def fetch_transactions():
    try:
        user_id = session.get('user_id')
        search_query = request.args.get('q', None)
        category_id = request.args.get('category_id', None)
        type_filter = request.args.get('type_filter', None)
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        sort_by = request.args.get('sort_by', 'transaction_date')
        sort_order = request.args.get('sort_order', 'DESC')
        
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        # Parse inputs
        if category_id and category_id.isdigit():
            category_id = int(category_id)
        else:
            category_id = None
            
        transactions = get_transactions(
            search_query, category_id, type_filter, start_date, end_date,
            sort_by, sort_order, offset, limit, user_id=user_id
        )
        
        total = get_transactions_count(search_query, category_id, type_filter, start_date, end_date, user_id=user_id)
        categories = get_all_categories()
        
        pages = math.ceil(total / limit) if total > 0 else 1
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "categories": categories,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": pages
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading transactions: {str(e)}"
        }), 500

@transaction_bp.route('/transaction/category', methods=['PUT'])
@login_required
def edit_category():
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        transaction_id = data.get('transaction_id')
        category_id = data.get('category_id')
        remember = data.get('remember', False)
        remember_amount = data.get('remember_amount', False)
        
        if not transaction_id or not category_id:
            return jsonify({"success": False, "message": "Transaction ID and Category ID are required."}), 400
            
        # Get transaction details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT description, merchant_name, payee_name, amount FROM transactions WHERE transaction_id = ? AND user_id = ?', (transaction_id, user_id))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"success": False, "message": "Transaction not found."}), 404
            
        desc = row['description']
        merchant = row['merchant_name']
        payee = row['payee_name']
        amount_val = row['amount']
        
        # Always update the category for the current transaction
        update_transaction_category(transaction_id, category_id, user_id=user_id)
        
        if remember:
            # Create rule for merchant or payee
            target_keyword = merchant if merchant else (payee if payee else desc)
            update_merchant_category_rules(target_keyword, category_id)
            
        if remember_amount:
            # Create amount-based rule
            try:
                amt_str = f"AMOUNT:{float(amount_val)}"
                update_merchant_category_rules(amt_str, category_id)
            except (ValueError, TypeError):
                pass
            
        return jsonify({
            "success": True,
            "message": "Category updated successfully."
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error updating category: {str(e)}"
        }), 500

@transaction_bp.route('/categories', methods=['GET'])
@login_required
def get_categories():
    try:
        categories = get_all_categories()
        return jsonify({
            "success": True,
            "categories": categories
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading categories: {str(e)}"
        }), 500
