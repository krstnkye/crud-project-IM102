import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).with_name("inventory.db")
LOW_STOCK_THRESHOLD = 10
MAX_QUANTITY = 1_000_000  # biggest stock allowed for one product
MAX_PRICE = 1_000_000  # biggest unit price allowed (PHP)


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def now_text():
    """The current date and time as text, like 2026-11-16 14:05:09."""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


@contextmanager
def database_connection():
    """Provide a transaction and always release the SQLite file handle."""
    connection = get_connection()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL CHECK(length(trim(product_name)) > 0),
                category TEXT NOT NULL CHECK(length(trim(category)) > 0),
                quantity INTEGER NOT NULL CHECK(quantity >= 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(username) BETWEEN 3 AND 20),
                full_name TEXT NOT NULL CHECK(length(trim(full_name)) > 0),
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


# ---------------------------------------------------------------- users


def create_user(username, full_name, password_hash):
    """Save a new user. Returns the new user_id, or None if the username is already taken."""
    try:
        with database_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, full_name, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, full_name, password_hash, now_text()),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username):
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT user_id, username, full_name, password_hash, created_at, last_login
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()


def set_password_hash(user_id, password_hash):
    with database_connection() as connection:
        connection.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (password_hash, user_id))


def record_login(user_id):
    with database_connection() as connection:
        connection.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now_text(), user_id))


def count_users():
    with database_connection() as connection:
        return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ---------------------------------------------------------------- activity log


def add_activity(user_id, action, details):
    with database_connection() as connection:
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_text()),
        )


def get_recent_activity(limit=50):
    """The newest saved actions, oldest first, with the username of who did them."""
    with database_connection() as connection:
        rows = connection.execute(
            """
            SELECT activity_log.log_id, activity_log.action, activity_log.details,
                   activity_log.created_at, users.username
            FROM activity_log
            LEFT JOIN users ON users.user_id = activity_log.user_id
            ORDER BY activity_log.log_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return list(reversed(rows))


# ---------------------------------------------------------------- products


def add_product(product_name, category, quantity, unit_price):
    product_name = product_name.strip()
    category = category.strip()

    with database_connection() as connection:
        existing_product = connection.execute(
            """
            SELECT product_id, quantity
            FROM products
            WHERE product_name = ? COLLATE NOCASE
              AND category = ? COLLATE NOCASE
              AND ROUND(unit_price, 2) = ROUND(?, 2)
            ORDER BY product_id
            LIMIT 1
            """,
            (product_name, category, unit_price),
        ).fetchone()

        if existing_product:
            if existing_product["quantity"] + quantity > MAX_QUANTITY:
                return "too_much"
            connection.execute(
                """
                UPDATE products
                SET quantity = quantity + ?
                WHERE product_id = ?
                """,
                (quantity, existing_product["product_id"]),
            )
            return "restocked"

        connection.execute(
            """
            INSERT INTO products (product_name, category, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            (product_name, category, quantity, unit_price),
        )
        return "created"


def get_products():
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT product_id, product_name, category, quantity, unit_price
            FROM products
            ORDER BY product_id DESC
            """
        ).fetchall()


def update_product(product_id, product_name, category, quantity, unit_price):
    product_name = product_name.strip()
    category = category.strip()

    with database_connection() as connection:
        duplicate = connection.execute(
            """
            SELECT product_id
            FROM products
            WHERE product_name = ? COLLATE NOCASE
              AND category = ? COLLATE NOCASE
              AND ROUND(unit_price, 2) = ROUND(?, 2)
              AND product_id != ?
            LIMIT 1
            """,
            (product_name, category, unit_price, product_id),
        ).fetchone()
        if duplicate:
            return "duplicate"

        cursor = connection.execute(
            """
            UPDATE products
            SET product_name = ?, category = ?, quantity = ?, unit_price = ?
            WHERE product_id = ?
            """,
            (product_name, category, quantity, unit_price, product_id),
        )
        return "updated" if cursor.rowcount else "missing"


def delete_product(product_id):
    """Delete one product. Returns False if it was already gone."""
    with database_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM products WHERE product_id = ?",
            (product_id,),
        )
        return cursor.rowcount > 0


def get_dashboard_totals():
    with database_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_products,
                COALESCE(SUM(quantity), 0) AS total_stock_units,
                SUM(CASE WHEN quantity < ? THEN 1 ELSE 0 END) AS low_stock_products,
                COALESCE(SUM(quantity * unit_price), 0) AS total_value
            FROM products
            """,
            (LOW_STOCK_THRESHOLD,),
        ).fetchone()

    return {
        "total_products": row["total_products"],
        "total_stock_units": row["total_stock_units"],
        "low_stock_products": row["low_stock_products"] or 0,
        "total_value": row["total_value"] or 0,
    }
