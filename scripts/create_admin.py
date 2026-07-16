from app import app
from database.models import create_user
from database.db import get_db_connection

with app.app_context():
    # Check if admin already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE email = 'admin@admin.com'")
    row = cursor.fetchone()
    
    if not row:
        user_id = create_user('admin@admin.com', 'Admin@1234', role='admin')
        print(f"Created admin user with ID: {user_id}")
    else:
        # Update existing user to admin role and reset password
        from werkzeug.security import generate_password_hash
        cursor.execute("UPDATE users SET role = 'admin', password_hash = %s, failed_attempts = 0, locked_until = NULL WHERE email = 'admin@admin.com'", (generate_password_hash('Admin@1234'),))
        conn.commit()
        print(f"Updated existing user admin@admin.com to admin role.")
    
    conn.close()
