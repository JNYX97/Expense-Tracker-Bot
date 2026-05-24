import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "expenses.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS expenses (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                amount           REAL    NOT NULL,
                category         TEXT    NOT NULL,
                category_type    TEXT    NOT NULL DEFAULT 'monthly',
                note             TEXT,
                date             TEXT    NOT NULL,
                period_month     INTEGER,
                period_year      INTEGER NOT NULL,
                is_recurring     INTEGER DEFAULT 0,
                recurrence_days  INTEGER DEFAULT 30
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                category       TEXT    NOT NULL,
                category_type  TEXT    NOT NULL DEFAULT 'monthly',
                period_limit   REAL    NOT NULL,
                period_month   INTEGER,
                period_year    INTEGER NOT NULL,
                UNIQUE(user_id, category, period_month, period_year)
            );
        """)
    init_projects_table()
    print("✅ Database initialised")


# ── Expenses ──────────────────────────────────────────────────────────────────

def insert_expense(user_id, amount, category, category_type,
                   note="", period_month=None, period_year=None,
                   is_recurring=False, recurrence_days=30):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    # Use first day of the period as the date stamp
    if category_type == "monthly":
        date_str = f"{period_year}-{period_month:02d}-01"
    else:
        date_str = f"{period_year}-01-01"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO expenses
               (user_id, amount, category, category_type, note,
                date, period_month, period_year, is_recurring, recurrence_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, amount, category.lower(), category_type, note,
             date_str, period_month, period_year, int(is_recurring), recurrence_days)
        )


def get_expenses_by_period(user_id, category_type="monthly",
                           period_month=None, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    if category_type == "monthly":
        query = """
            SELECT amount, category, category_type, note, date, is_recurring,
                   period_month, period_year
            FROM expenses
            WHERE user_id = ? AND category_type = ?
              AND period_month = ? AND period_year = ?
            ORDER BY date DESC
        """
        params = [user_id, category_type, period_month, period_year]
    else:
        query = """
            SELECT amount, category, category_type, note, date, is_recurring,
                   period_month, period_year
            FROM expenses
            WHERE user_id = ? AND category_type = ? AND period_year = ?
            ORDER BY date DESC
        """
        params = [user_id, category_type, period_year]

    with get_conn() as conn:
        return conn.execute(query, params).fetchall()


def get_recurring_expenses(user_id, category_type=None):
    query = """
        SELECT amount, category, category_type, note, recurrence_days
        FROM expenses
        WHERE user_id = ? AND is_recurring = 1
    """
    params = [user_id]
    if category_type:
        query += " AND category_type = ?"
        params.append(category_type)
    with get_conn() as conn:
        return conn.execute(query, params).fetchall()


def get_period_totals_by_category(user_id, category_type="monthly",
                                   period_month=None, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    if category_type == "monthly":
        query = """
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND category_type = ?
              AND period_month = ? AND period_year = ?
            GROUP BY category
        """
        params = [user_id, category_type, period_month, period_year]
    else:
        query = """
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND category_type = ? AND period_year = ?
            GROUP BY category
        """
        params = [user_id, category_type, period_year]

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return {row[0]: row[1] for row in rows}


# ── Budgets ───────────────────────────────────────────────────────────────────

def set_budget_db(user_id, category, category_type, period_limit,
                  period_month=None, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO budgets
               (user_id, category, category_type, period_limit, period_month, period_year)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, category, period_month, period_year)
               DO UPDATE SET period_limit = excluded.period_limit""",
            (user_id, category.lower(), category_type, period_limit,
             period_month, period_year)
        )


def get_budgets(user_id, category_type=None, period_month=None, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    if period_month is None and category_type == "monthly":
        period_month = now.month

    if category_type == "monthly":
        query = """
            SELECT category, category_type, period_limit, period_month, period_year
            FROM budgets
            WHERE user_id = ? AND category_type = ?
              AND period_month = ? AND period_year = ?
        """
        params = [user_id, category_type, period_month, period_year]
    elif category_type == "annual":
        query = """
            SELECT category, category_type, period_limit, period_month, period_year
            FROM budgets
            WHERE user_id = ? AND category_type = ? AND period_year = ?
        """
        params = [user_id, category_type, period_year]
    else:
        query = """
            SELECT category, category_type, period_limit, period_month, period_year
            FROM budgets WHERE user_id = ?
        """
        params = [user_id]

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return {row[0]: {"type": row[1], "limit": row[2],
                     "month": row[3], "year": row[4]} for row in rows}


# ── Projects (subcategories of "project") ─────────────────────────────────────

def create_project(user_id, project_name, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO projects
               (user_id, project_name, period_year)
               VALUES (?, ?, ?)""",
            (user_id, project_name.strip(), period_year)
        )


def init_projects_table():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                project_name TEXT    NOT NULL,
                period_year  INTEGER NOT NULL,
                budget       REAL    DEFAULT NULL,
                UNIQUE(user_id, project_name, period_year)
            );

            CREATE TABLE IF NOT EXISTS project_expenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                project_name TEXT    NOT NULL,
                period_year  INTEGER NOT NULL,
                amount       REAL    NOT NULL,
                note         TEXT,
                date         TEXT    NOT NULL DEFAULT (DATE('now'))
            );
        """)


def set_project_budget(user_id, project_name, period_year, budget):
    with get_conn() as conn:
        # Ensure project exists first
        conn.execute(
            """INSERT OR IGNORE INTO projects (user_id, project_name, period_year)
               VALUES (?, ?, ?)""",
            (user_id, project_name.strip(), period_year)
        )
        conn.execute(
            """UPDATE projects SET budget = ?
               WHERE user_id = ? AND project_name = ? AND period_year = ?""",
            (budget, user_id, project_name.strip(), period_year)
        )


def get_projects(user_id, period_year=None):
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT project_name, period_year, budget
               FROM projects
               WHERE user_id = ? AND period_year = ?
               ORDER BY project_name""",
            (user_id, period_year)
        ).fetchall()
    return [{"name": r[0], "year": r[1], "budget": r[2]} for r in rows]


def get_project(user_id, project_name, period_year):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT project_name, period_year, budget
               FROM projects
               WHERE user_id = ? AND project_name = ? AND period_year = ?""",
            (user_id, project_name.strip(), period_year)
        ).fetchone()
    if row:
        return {"name": row[0], "year": row[1], "budget": row[2]}
    return None


def insert_project_expense(user_id, project_name, period_year, amount, note=""):
    now = datetime.now()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO project_expenses
               (user_id, project_name, period_year, amount, note, date)
               VALUES (?, ?, ?, ?, ?, DATE('now'))""",
            (user_id, project_name.strip(), period_year, amount, note)
        )
        # Also insert into main expenses table so /summary annual picks it up
        conn.execute(
            """INSERT INTO expenses
               (user_id, amount, category, category_type, note,
                date, period_month, period_year, is_recurring, recurrence_days)
               VALUES (?, ?, 'project', 'annual', ?, DATE('now'), NULL, ?, 0, 365)""",
            (user_id, amount, f"[{project_name.strip()}] {note}".strip(), period_year)
        )


def get_project_expenses(user_id, project_name, period_year):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT amount, note, date
               FROM project_expenses
               WHERE user_id = ? AND project_name = ? AND period_year = ?
               ORDER BY date DESC""",
            (user_id, project_name.strip(), period_year)
        ).fetchall()
    return [{"amount": r[0], "note": r[1], "date": r[2]} for r in rows]


def get_project_totals(user_id, period_year=None):
    """Returns {project_name: total_spent} for a given year."""
    now = datetime.now()
    if period_year is None:
        period_year = now.year
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT project_name, SUM(amount)
               FROM project_expenses
               WHERE user_id = ? AND period_year = ?
               GROUP BY project_name""",
            (user_id, period_year)
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def delete_project(user_id, project_name, period_year):
    with get_conn() as conn:
        conn.execute(
            """DELETE FROM projects
               WHERE user_id = ? AND project_name = ? AND period_year = ?""",
            (user_id, project_name.strip(), period_year)
        )
        conn.execute(
            """DELETE FROM project_expenses
               WHERE user_id = ? AND project_name = ? AND period_year = ?""",
            (user_id, project_name.strip(), period_year)
        )
