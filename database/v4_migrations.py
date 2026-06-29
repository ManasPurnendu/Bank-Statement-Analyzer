#!/usr/bin/env python3
"""Database migration script (v4) to add income_intelligence_reports table.
Run with: python -m database.v4_migrations
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bank_statement.db')

def enable_foreign_keys(conn):
    conn.execute('PRAGMA foreign_keys = ON')

def create_intelligence_reports_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS income_intelligence_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            statement_id INTEGER,
            engine_version TEXT NOT NULL,
            data_sufficiency_grade TEXT,
            eligibility_status TEXT NOT NULL,
            base_salary REAL,
            fixed_emi_obligations REAL,
            foir_percentage REAL,
            stability_score REAL,
            statement_health_score REAL,
            surplus_score REAL,
            buffer_score REAL,
            final_readiness_score REAL,
            risk_flags TEXT,
            positive_signals TEXT,
            report_generation_time_ms REAL,
            calculation_metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    print('Created income_intelligence_reports table')

def create_indexes(conn):
    conn.execute('CREATE INDEX IF NOT EXISTS idx_reports_user_id ON income_intelligence_reports(user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_reports_statement_id ON income_intelligence_reports(statement_id)')
    conn.commit()
    print('Indexes created')

def main():
    conn = sqlite3.connect(DB_PATH)
    enable_foreign_keys(conn)
    create_intelligence_reports_table(conn)
    create_indexes(conn)
    conn.close()
    print('Migration v4 completed')

if __name__ == '__main__':
    main()
