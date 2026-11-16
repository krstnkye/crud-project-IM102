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
                unit_price REAL NOT NULL CHECK(unit_price >= 0),
                created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                created_at TEXT,
                updated_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                updated_at TEXT
            )
            """
        )
        # Databases made before accounts existed: add the "who and when" columns, keeping every product.
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
        for column, kind in (
            ("created_by", "INTEGER REFERENCES users(user_id) ON DELETE SET NULL"),
            ("created_at", "TEXT"),
            ("updated_by", "INTEGER REFERENCES users(user_id) ON DELETE SET NULL"),
            ("updated_at", "TEXT"),
        ):
            if column not in existing:
                connection.execute(f"ALTER TABLE products ADD COLUMN {column} {kind}")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(username) BETWEEN 3 AND 20),
                full_name TEXT NOT NULL CHECK(length(trim(full_name)) > 0),
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('admin', 'staff')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
            )
            """
        )
        # Databases made before roles existed: add the columns and make the first account the admin.
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "role" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('admin', 'staff'))"
            )
        if "is_active" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))"
            )
        has_admin = connection.execute("SELECT 1 FROM users WHERE role = 'admin' AND is_active = 1").fetchone()
        if not has_admin:
            connection.execute(
                "UPDATE users SET role = 'admin', is_active = 1 WHERE user_id = (SELECT MIN(user_id) FROM users)"
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


def create_user(username, full_name, password_hash, role="staff"):
    """Save a new user. Returns the new user_id, or None if the username is already taken."""
    try:
        with database_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, full_name, password_hash, created_at, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, full_name, password_hash, now_text(), role),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username):
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT user_id, username, full_name, password_hash, created_at, last_login, role, is_active
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()


def update_full_name(user_id, full_name):
    with database_connection() as connection:
        connection.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (full_name, user_id))


def get_user_by_id(user_id):
    with database_connection() as connection:
        return connection.execute(
            "SELECT user_id, username, full_name, password_hash, created_at, last_login, role, is_active FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def set_role(user_id, role):
    with database_connection() as connection:
        connection.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))


def set_active(user_id, active):
    with database_connection() as connection:
        connection.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if active else 0, user_id))


def count_active_admins():
    with database_connection() as connection:
        return connection.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1").fetchone()[0]


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


PRODUCT_ACTIONS = ("ADD", "RESTOCK", "UPDATE", "DELETE")


def get_user_activity(user_id, limit=100):
    """One user's saved actions, newest first."""
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT log_id, action, details, created_at
            FROM activity_log
            WHERE user_id = ?
            ORDER BY log_id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


def get_user_stats(user_id):
    """How many products this user added, restocked, updated, and deleted."""
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT action, COUNT(*) AS total FROM activity_log WHERE user_id = ? GROUP BY action",
            (user_id,),
        ).fetchall()
        last = connection.execute(
            f"""
            SELECT created_at FROM activity_log
            WHERE user_id = ? AND action IN ({",".join("?" * len(PRODUCT_ACTIONS))})
            ORDER BY log_id DESC LIMIT 1
            """,
            (user_id, *PRODUCT_ACTIONS),
        ).fetchone()
    counts = {row["action"]: row["total"] for row in rows}
    stats = {action: counts.get(action, 0) for action in PRODUCT_ACTIONS}
    stats["total"] = sum(stats.values())
    stats["last_change"] = last["created_at"] if last else None
    return stats


def get_team_summary():
    """Every user with their number of product changes and last sign-in, for the user list."""
    with database_connection() as connection:
        return connection.execute(
            f"""
            SELECT users.user_id, users.username, users.full_name, users.created_at, users.last_login,
                   users.role, users.is_active,
                   COUNT(activity_log.log_id) AS changes,
                   MAX(activity_log.created_at) AS last_change
            FROM users
            LEFT JOIN activity_log
              ON activity_log.user_id = users.user_id
             AND activity_log.action IN ({",".join("?" * len(PRODUCT_ACTIONS))})
            GROUP BY users.user_id
            ORDER BY users.role, changes DESC, users.username COLLATE NOCASE
            """,
            PRODUCT_ACTIONS,
        ).fetchall()


def get_all_activity(limit=200, product_changes_only=False):
    """Everyone's saved actions, newest first, for the Admin Dashboard."""
    where = f"WHERE activity_log.action IN ({','.join('?' * len(PRODUCT_ACTIONS))})" if product_changes_only else ""
    parameters = (*PRODUCT_ACTIONS, limit) if product_changes_only else (limit,)
    with database_connection() as connection:
        return connection.execute(
            f"""
            SELECT activity_log.log_id, activity_log.action, activity_log.details, activity_log.created_at,
                   users.username, users.user_id
            FROM activity_log
            LEFT JOIN users ON users.user_id = activity_log.user_id
            {where}
            ORDER BY activity_log.log_id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()


def count_changes_since(moment_text):
    with database_connection() as connection:
        return connection.execute(
            f"SELECT COUNT(*) FROM activity_log WHERE created_at >= ? AND action IN ({','.join('?' * len(PRODUCT_ACTIONS))})",
            (moment_text, *PRODUCT_ACTIONS),
        ).fetchone()[0]


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


def add_product(product_name, category, quantity, unit_price, user_id=None):
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
                SET quantity = quantity + ?, updated_by = ?, updated_at = ?
                WHERE product_id = ?
                """,
                (quantity, user_id, now_text(), existing_product["product_id"]),
            )
            return "restocked"

        connection.execute(
            """
            INSERT INTO products (product_name, category, quantity, unit_price, created_by, created_at, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product_name, category, quantity, unit_price, user_id, now_text(), user_id, now_text()),
        )
        return "created"


def get_products():
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT products.product_id, products.product_name, products.category, products.quantity,
                   products.unit_price, products.created_at, products.updated_at,
                   creator.username AS created_by_name, editor.username AS updated_by_name
            FROM products
            LEFT JOIN users AS creator ON creator.user_id = products.created_by
            LEFT JOIN users AS editor ON editor.user_id = products.updated_by
            ORDER BY products.product_id DESC
            """
        ).fetchall()


def update_product(product_id, product_name, category, quantity, unit_price, user_id=None):
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
            SET product_name = ?, category = ?, quantity = ?, unit_price = ?, updated_by = ?, updated_at = ?
            WHERE product_id = ?
            """,
            (product_name, category, quantity, unit_price, user_id, now_text(), product_id),
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
