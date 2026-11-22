import sqlite3
from contextlib import contextmanager
from datetime import datetime
import time
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
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                photo BLOB,
                must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0, 1))
            )
            """
        )
        # Databases made before roles existed: add the columns and make the first account the admin.
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        role_was_missing = "role" not in user_columns
        if role_was_missing:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('admin', 'staff'))"
            )
        if "is_active" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))"
            )
        if "photo" not in user_columns:
            # Profile photos are saved inside inventory.db, so no extra folder is needed.
            connection.execute("ALTER TABLE users ADD COLUMN photo BLOB")
        if "must_change_password" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0 "
                "CHECK(must_change_password IN (0, 1))"
            )
        if role_was_missing:
            connection.execute(
                "UPDATE users SET role = 'admin', is_active = 1 WHERE user_id = (SELECT MIN(user_id) FROM users)"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS registration_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE CHECK(length(username) BETWEEN 3 AND 20),
                full_name TEXT NOT NULL CHECK(length(trim(full_name)) > 0),
                password_hash TEXT NOT NULL,
                requested_role TEXT NOT NULL CHECK(requested_role IN ('admin', 'staff')),
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                failures INTEGER NOT NULL DEFAULT 0 CHECK(failures >= 0),
                locked_until REAL NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS registration_requests_pending_username
            ON registration_requests(username COLLATE NOCASE)
            WHERE status = 'pending'
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


def create_initial_admin(username, full_name, password_hash):
    """Create the first administrator atomically, even if two app windows race."""
    try:
        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                return "already_initialized"
            cursor = connection.execute(
                "INSERT INTO users (username, full_name, password_hash, created_at, role) "
                "VALUES (?, ?, ?, ?, 'admin')",
                (username, full_name, password_hash, now_text()),
            )
            connection.execute(
                "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'SIGN UP', ?, ?)",
                (cursor.lastrowid, f"Admin account created for {full_name}.", now_text()),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username):
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT user_id, username, full_name, password_hash, created_at, last_login, role, is_active,
                   must_change_password
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
            "SELECT user_id, username, full_name, password_hash, created_at, last_login, role, is_active, "
            "must_change_password FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def get_photo(user_id):
    """The user's profile photo as bytes (PNG or GIF), or None if they have not added one."""
    with database_connection() as connection:
        row = connection.execute("SELECT photo FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return bytes(row["photo"]) if row and row["photo"] else None


def set_photo(user_id, data):
    """Save a profile photo (bytes), or remove it when data is None."""
    with database_connection() as connection:
        connection.execute("UPDATE users SET photo = ? WHERE user_id = ?", (sqlite3.Binary(data) if data else None, user_id))


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


def change_own_password(user_id, password_hash):
    with database_connection() as connection:
        cursor = connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 "
            "WHERE user_id = ? AND is_active = 1",
            (password_hash, user_id),
        )
        return cursor.rowcount > 0


def get_login_state(username):
    with database_connection() as connection:
        row = connection.execute(
            "SELECT failures, locked_until FROM login_attempts WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
    return (row["failures"], row["locked_until"]) if row else (0, 0.0)


def record_failed_login(username, maximum, lockout_seconds):
    """Persist a failed attempt and return (attempts_left, locked_until)."""
    key = username.strip().lower()
    now = time.time()
    with database_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT failures, locked_until FROM login_attempts WHERE username = ? COLLATE NOCASE", (key,)
        ).fetchone()
        if row and row["locked_until"] > now:
            return 0, row["locked_until"]
        failures = (row["failures"] if row else 0) + 1
        locked_until = now + lockout_seconds if failures >= maximum else 0.0
        saved_failures = 0 if locked_until else failures
        connection.execute(
            "INSERT INTO login_attempts (username, failures, locked_until) VALUES (?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET failures = excluded.failures, locked_until = excluded.locked_until",
            (key, saved_failures, locked_until),
        )
        return max(0, maximum - failures), locked_until


def clear_login_attempts(username):
    with database_connection() as connection:
        connection.execute("DELETE FROM login_attempts WHERE username = ? COLLATE NOCASE", (username.strip(),))


def record_login(user_id):
    with database_connection() as connection:
        connection.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now_text(), user_id))


def count_users():
    with database_connection() as connection:
        return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def admin_create_user(actor_id, username, full_name, password_hash, role):
    """Create an account only when the actor is still an active administrator."""
    try:
        with database_connection() as connection:
            actor = connection.execute(
                "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (actor_id,)
            ).fetchone()
            if not actor or actor["role"] != "admin" or not actor["is_active"] or actor["must_change_password"]:
                return "forbidden"
            cursor = connection.execute(
                "INSERT INTO users (username, full_name, password_hash, created_at, role) VALUES (?, ?, ?, ?, ?)",
                (username, full_name, password_hash, now_text(), role),
            )
            role_name = "Admin" if role == "admin" else "Staff"
            connection.execute(
                "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'ACCOUNT', ?, ?)",
                (actor_id, f"Created {role_name} account @{username} for {full_name}.", now_text()),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return "username_exists"


def admin_set_role(actor_id, target_id, role):
    with database_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        actor = connection.execute(
            "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (actor_id,)
        ).fetchone()
        target = connection.execute(
            "SELECT username, role, is_active FROM users WHERE user_id = ?", (target_id,)
        ).fetchone()
        if not actor or actor["role"] != "admin" or not actor["is_active"] or actor["must_change_password"]:
            return "forbidden"
        if not target:
            return "missing"
        if target["role"] == role:
            return "unchanged"
        if role == "staff" and target["role"] == "admin" and target["is_active"]:
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                return "last_admin"
        connection.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, target_id))
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'ROLE', ?, ?)",
            (actor_id, f"Made @{target['username']} {'an Admin' if role == 'admin' else 'Staff'}.", now_text()),
        )
        return "updated"


def admin_set_active(actor_id, target_id, active):
    with database_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        actor = connection.execute(
            "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (actor_id,)
        ).fetchone()
        target = connection.execute(
            "SELECT username, role, is_active FROM users WHERE user_id = ?", (target_id,)
        ).fetchone()
        if not actor or actor["role"] != "admin" or not actor["is_active"] or actor["must_change_password"]:
            return "forbidden"
        if not target:
            return "missing"
        if not active and actor_id == target_id:
            return "self"
        if not active and target["role"] == "admin" and target["is_active"]:
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                return "last_admin"
        connection.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if active else 0, target_id))
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'ACCOUNT', ?, ?)",
            (actor_id, f"{'Activated' if active else 'Deactivated'} the account of @{target['username']}.", now_text()),
        )
        return "updated"


def admin_reset_password(actor_id, target_id, password_hash):
    with database_connection() as connection:
        actor = connection.execute(
            "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (actor_id,)
        ).fetchone()
        target = connection.execute("SELECT username FROM users WHERE user_id = ?", (target_id,)).fetchone()
        if not actor or actor["role"] != "admin" or not actor["is_active"] or actor["must_change_password"]:
            return "forbidden"
        if not target:
            return "missing"
        connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE user_id = ?",
            (password_hash, target_id),
        )
        connection.execute("DELETE FROM login_attempts WHERE username = ? COLLATE NOCASE", (target["username"],))
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'PASSWORD', ?, ?)",
            (actor_id, f"Reset the password of @{target['username']}.", now_text()),
        )
        return target["username"]


# ---------------------------------------------------------- registration requests


def submit_registration_request(username, full_name, password_hash, requested_role):
    """Save a pending request. Returns its id or a short duplicate reason."""
    try:
        with database_connection() as connection:
            if connection.execute(
                "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone():
                return "username_exists"
            cursor = connection.execute(
                """
                INSERT INTO registration_requests
                    (username, full_name, password_hash, requested_role, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (username, full_name, password_hash, requested_role, now_text()),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return "pending_exists"


def get_pending_registration_requests():
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT request_id, username, full_name, requested_role, created_at
            FROM registration_requests
            WHERE status = 'pending'
            ORDER BY request_id
            """
        ).fetchall()


def pending_registration_exists(username):
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT 1 FROM registration_requests
            WHERE username = ? COLLATE NOCASE AND status = 'pending'
            """,
            (username.strip(),),
        ).fetchone() is not None


def approve_registration_request(request_id, reviewer_id, role):
    """Atomically approve one pending request and create its account."""
    with database_connection() as connection:
        reviewer = connection.execute(
            "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (reviewer_id,)
        ).fetchone()
        if reviewer is None or reviewer["role"] != "admin" or not reviewer["is_active"] or reviewer["must_change_password"]:
            return "forbidden"
        request = connection.execute(
            "SELECT * FROM registration_requests WHERE request_id = ? AND status = 'pending'",
            (request_id,),
        ).fetchone()
        if request is None:
            return None
        try:
            cursor = connection.execute(
                """
                INSERT INTO users (username, full_name, password_hash, created_at, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (request["username"], request["full_name"], request["password_hash"], now_text(), role),
            )
        except sqlite3.IntegrityError:
            return "username_exists"
        connection.execute(
            """
            UPDATE registration_requests
            SET status = 'approved', password_hash = '', reviewed_at = ?, reviewed_by = ?
            WHERE request_id = ?
            """,
            (now_text(), reviewer_id, request_id),
        )
        role_name = "Admin" if role == "admin" else "Staff"
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'ACCOUNT', ?, ?)",
            (reviewer_id, f"Approved {role_name} account request @{request['username']} for {request['full_name']}.", now_text()),
        )
        return cursor.lastrowid, request["username"], request["full_name"]


def reject_registration_request(request_id, reviewer_id):
    """Reject one pending request and discard its saved password hash."""
    with database_connection() as connection:
        reviewer = connection.execute(
            "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (reviewer_id,)
        ).fetchone()
        if reviewer is None or reviewer["role"] != "admin" or not reviewer["is_active"] or reviewer["must_change_password"]:
            return "forbidden"
        request = connection.execute(
            "SELECT * FROM registration_requests WHERE request_id = ? AND status = 'pending'",
            (request_id,),
        ).fetchone()
        if request is None:
            return None
        connection.execute(
            """
            UPDATE registration_requests
            SET status = 'rejected', password_hash = '', reviewed_at = ?, reviewed_by = ?
            WHERE request_id = ?
            """,
            (now_text(), reviewer_id, request_id),
        )
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, 'ACCOUNT', ?, ?)",
            (reviewer_id, f"Rejected account request @{request['username']} for {request['full_name']}.", now_text()),
        )
        return request["username"], request["full_name"]


# ---------------------------------------------------------------- activity log


def add_activity(user_id, action, details):
    with database_connection() as connection:
        connection.execute(
            "INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_text()),
        )


PRODUCT_ACTIONS = ("ADD", "RESTOCK", "UPDATE", "DELETE")

# How saved actions are shown on screen. The short codes saved in activity_log do not change.
ACTION_LABELS = {"RESTOCK": "ADD STOCK", "ALERT": "LOW STOCK", "START": "WELCOME", "THEME": "DISPLAY"}


def action_label(action):
    return ACTION_LABELS.get(action, action)


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
        if user_id is not None:
            actor = connection.execute(
                "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not actor or not actor["is_active"] or actor["must_change_password"] or actor["role"] not in ("admin", "staff"):
                return "forbidden"
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
        if user_id is not None:
            actor = connection.execute(
                "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not actor or not actor["is_active"] or actor["must_change_password"] or actor["role"] not in ("admin", "staff"):
                return "forbidden"
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


def delete_product(product_id, user_id=None):
    """Delete one product. Returns False if it was already gone."""
    with database_connection() as connection:
        if user_id is not None:
            actor = connection.execute(
                "SELECT role, is_active, must_change_password FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not actor or not actor["is_active"] or actor["must_change_password"] or actor["role"] != "admin":
                return "forbidden"
        cursor = connection.execute(
            "DELETE FROM products WHERE product_id = ?",
            (product_id,),
        )
        return "deleted" if cursor.rowcount else "missing"


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
