from functools import wraps
from flask import session, redirect, url_for, abort, request, jsonify

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Unauthorized"}), 401
            return redirect(url_for('auth.login_page'))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Unauthorized"}), 401
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Forbidden"}), 403
            abort(403)
        return fn(*args, **kwargs)
    return wrapper
