import random
from datetime import datetime, timedelta
import sqlite3
import os
import sys

# Add project root to sys.path so we can import app modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import get_db_connection

def random_date(start_date: datetime, end_date: datetime) -> datetime:
    """Generate a random date between start and end."""
    time_between = end_date - start_date
    days_between = time_between.days
    random_number_of_days = random.randrange(days_between + 1)
    return start_date + timedelta(days=random_number_of_days)

def get_random_time(date_obj: datetime) -> datetime:
    """Assign a random time to a date."""
    hour = random.randint(7, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return date_obj.replace(hour=hour, minute=minute, second=second)

def is_weekend(date_obj: datetime) -> bool:
    return date_obj.weekday() >= 5

def is_month_end(date_obj: datetime) -> bool:
    return date_obj.day >= 25

def is_month_start(date_obj: datetime) -> bool:
    return date_obj.day <= 5

def generate_transaction_hash(user_id, date, amount, desc):
    """Generate a pseudo-unique hash for the transaction to satisfy DB constraints."""
    import hashlib
    raw_str = f"{user_id}_{date}_{amount}_{desc}_{random.random()}"
    return hashlib.sha256(raw_str.encode()).hexdigest()

def get_db():
    return get_db_connection()
