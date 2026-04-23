import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'student_expense_secret_2024'

# Custom Jinja2 filter – returns today's date as YYYY-MM-DD
@app.template_filter('today_date')
def today_date_filter(s):
    return date.today().isoformat()

# ─────────────────────────────────────────────
#  MySQL Configuration  –  from environment variables
# ─────────────────────────────────────────────
DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'expense_tracker')
}


# ─────────────────────────────────────────────
#  Database helpers
# ─────────────────────────────────────────────
def get_db():
    """Return a new MySQL connection with dictionary cursor support."""
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn


def init_db():
    """Create the database and all tables from schema.sql if not already present."""
    import re

    # Step 1: Connect WITHOUT a database to create it
    base_cfg = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    conn   = mysql.connector.connect(**base_cfg)
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS expense_tracker")
    cursor.close()
    conn.close()

    # Step 2: Connect WITH the database and run the full schema
    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    with open('schema.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    # Remove single-line SQL comments
    sql = re.sub(r'--[^\n]*', '', sql)

    # Drop CREATE DATABASE / USE lines (already handled above)
    sql = re.sub(r'(?i)CREATE\s+DATABASE[^;]*;', '', sql)
    sql = re.sub(r'(?i)USE\s+\w+\s*;', '', sql)

    # Execute all statements using multi=True equivalent (manual split)
    for stmt in sql.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt)
                if cursor.with_rows:
                    cursor.fetchall()
            except mysql.connector.Error as e:
                # Ignore errors like "Duplicate column name" or "Table already exists"
                pass

    # --- NEW: Cleanup duplicates and enforce UNIQUE constraint ---
    try:
        # 1. Delete duplicates keep only the one with the smallest ID
        cursor.execute("""
            DELETE t1 FROM categories t1
            INNER JOIN categories t2 
            WHERE t1.id > t2.id AND t1.name = t2.name
        """)
        
        # 2. Add UNIQUE constraint if it doesn't exist
        # We try-catch this because if it already exists, MySQL will throw an error
        try:
            cursor.execute("ALTER TABLE categories ADD UNIQUE INDEX unique_category_name (name)")
        except mysql.connector.Error:
            pass # Already exists
            
    except mysql.connector.Error as e:
        print(f"  [Error during cleanup] {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("[✓] MySQL database and tables ready (Category duplicates fixed)")


# ─────────────────────────────────────────────
#  Auth routes
# ─────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip()
        password = request.form['password']

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    name     = request.form['name'].strip()
    email    = request.form['email'].strip()
    password = request.form['password']

    if not name or not email or not password:
        flash('All fields are required.', 'error')
        return redirect(url_for('login'))

    hashed = generate_password_hash(password)

    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Account created! Please log in.', 'success')
    except mysql.connector.IntegrityError:
        flash('Email already registered.', 'error')

    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid   = session['user_id']
    today = date.today()
    month = today.month
    year  = today.year

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)

    # Total spent this month
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE user_id = %s
          AND MONTH(date) = %s
          AND YEAR(date)  = %s
    """, (uid, month, year))
    total_month = cursor.fetchone()['total']

    # Recent 5 expenses
    cursor.execute("""
        SELECT e.id, e.amount, e.description, e.date, e.payment_method,
               c.name AS category, c.icon, c.color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
        ORDER BY e.date DESC, e.id DESC
        LIMIT 5
    """, (uid,))
    recent = cursor.fetchall()

    # Spending by category this month
    cursor.execute("""
        SELECT c.name, c.icon, c.color,
               COALESCE(SUM(e.amount), 0) AS total
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
          AND MONTH(e.date) = %s
          AND YEAR(e.date)  = %s
        GROUP BY c.id, c.name, c.icon, c.color
        ORDER BY total DESC
    """, (uid, month, year))
    by_category = cursor.fetchall()

    # Monthly totals for last 6 months (bar chart)
    cursor.execute("""
        SELECT DATE_FORMAT(date, '%%Y-%%m') AS ym,
               SUM(amount) AS total
        FROM expenses
        WHERE user_id = %s
          AND date >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 5 MONTH), '%%Y-%%m-01')
        GROUP BY ym
        ORDER BY ym
    """, (uid,))
    monthly_data = cursor.fetchall()

    # Budget summary with spending
    cursor.execute("""
        SELECT b.limit_amount, c.name, c.color,
               COALESCE((
                   SELECT SUM(e.amount) FROM expenses e
                   WHERE e.category_id = b.category_id
                     AND e.user_id = b.user_id
                     AND MONTH(e.date) = %s
                     AND YEAR(e.date)  = %s
               ), 0) AS spent
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = %s AND b.month = %s AND b.year = %s
    """, (month, year, uid, month, year))
    budgets = cursor.fetchall()

    # All categories for modal
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('dashboard.html',
        total_month=total_month,
        recent=recent,
        by_category=by_category,
        monthly_data=monthly_data,
        budgets=budgets,
        categories=categories,
        month_name=today.strftime('%B'),
        year=year
    )


# ─────────────────────────────────────────────
#  Expenses
# ─────────────────────────────────────────────
@app.route('/expenses')
def expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid          = session['user_id']
    cat_filter   = request.args.get('category', '')
    month_filter = request.args.get('month', '')

    query  = """
        SELECT e.id, e.amount, e.description, e.date, e.payment_method,
               c.name AS category, c.icon, c.color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
    """
    params = [uid]

    if cat_filter:
        query += " AND e.category_id = %s"
        params.append(cat_filter)

    if month_filter:
        query += " AND DATE_FORMAT(e.date, '%%Y-%%m') = %s"
        params.append(month_filter)

    query += " ORDER BY e.date DESC, e.id DESC"

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, params)
    expense_list = cursor.fetchall()

    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()

    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s",
        (uid,)
    )
    total = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    return render_template('expenses.html',
        expense_list=expense_list,
        categories=categories,
        total=total,
        cat_filter=cat_filter,
        month_filter=month_filter
    )


@app.route('/expenses/add', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid            = session['user_id']
    amount         = request.form.get('amount', type=float)
    category_id    = request.form.get('category_id') or None
    description    = request.form.get('description', '').strip()
    exp_date       = request.form.get('date', date.today().isoformat())
    payment_method = request.form.get('payment_method', 'Cash')

    if not amount or amount <= 0:
        flash('Please enter a valid amount.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, category_id, amount, description, date, payment_method)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (uid, category_id, amount, description, exp_date, payment_method))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Expense added successfully!', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/expenses/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid    = session['user_id']
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM expenses WHERE id = %s AND user_id = %s",
        (expense_id, uid)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash('Expense deleted.', 'success')
    return redirect(request.referrer or url_for('expenses'))


# ─────────────────────────────────────────────
#  Budgets
# ─────────────────────────────────────────────
@app.route('/budget/set', methods=['POST'])
def set_budget():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid         = session['user_id']
    category_id = request.form.get('category_id')
    limit_amt   = request.form.get('limit_amount', type=float)
    month_year  = request.form.get('month_year', '')

    if month_year:
        year, month = month_year.split('-')
        month, year = int(month), int(year)
    else:
        month = date.today().month
        year  = date.today().year

    if not limit_amt or limit_amt <= 0:
        flash('Enter a valid budget amount.', 'error')
        return redirect(url_for('dashboard'))

    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budgets (user_id, category_id, limit_amount, month, year)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE limit_amount = VALUES(limit_amount)
    """, (uid, category_id, limit_amt, month, year))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Budget saved!', 'success')
    return redirect(url_for('dashboard'))


# ─────────────────────────────────────────────
#  Expert Corner
# ─────────────────────────────────────────────
@app.route('/expert')
def expert():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Curated tips for students
    tips = [
        {
            'book': 'Atomic Habits',
            'author': 'James Clear',
            'tip': 'The 1% Rule',
            'content': 'Don\'t try to save 50% of your allowance at once. Start by saving just 1% more than last month. Consistency builds the identity of a "saver".',
            'color': '#fbbf24'
        },
        {
            'book': 'The Psychology of Money',
            'author': 'Morgan Housel',
            'tip': 'Wealth is what you don\'t see',
            'content': 'Spending money to show people how much money you have is the fastest way to have less money. Focus on freedom, not status.',
            'color': '#f43f5e'
        },
        {
            'book': 'Rich Dad Poor Dad',
            'author': 'Robert Kiyosaki',
            'tip': 'Assets vs Liabilities',
            'content': 'An asset puts money in your pocket. A liability takes money out. For a student, a skill is your biggest asset. Invest in learning.',
            'color': '#10b981'
        },
        {
            'book': 'The 50/30/20 Rule',
            'author': 'Elizabeth Warren',
            'tip': 'The Golden Ratio',
            'content': 'Aim to spend 50% on Needs, 30% on Wants, and save 20%. As a student, even 80/10/10 is a great start!',
            'color': '#6366f1'
        }
    ]
    
    return render_template('expert.html', tips=tips)


# ─────────────────────────────────────────────
#  Run
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
