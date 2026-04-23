import mysql.connector

DB_CONFIG = {
    'host':     'localhost',
    'user':     'root',
    'password': 'Student12@',
    'database': 'expense_tracker'
}

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    print("Database connection successful!")
    conn.close()
except Exception as e:
    print(f"Database connection failed: {e}")
