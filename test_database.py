"""Automatic tests for the Product Inventory System.

Run them from the project folder with:

    python -m unittest test_database.py

The tests use a temporary database file, so your real inventory.db is not touched.
"""

import gc
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path

import auth
import database
import database_viewer
from main import parse_price, parse_quantity
from validation import ValidationError, validate_product, validate_sign_up


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.real_path = database.DB_PATH
        self.real_viewer_path = database_viewer.DB_PATH
        database.DB_PATH = Path(self.folder.name) / "test_inventory.db"
        database_viewer.DB_PATH = database.DB_PATH
        database.initialize_database()

    def tearDown(self):
        database.DB_PATH = self.real_path
        database_viewer.DB_PATH = self.real_viewer_path
        self.folder.cleanup()

    def test_database_viewer_closes_its_connection(self):
        viewer = database_viewer.DatabaseViewer.__new__(database_viewer.DatabaseViewer)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            viewer.column_types()
            gc.collect()

        resource_warnings = [warning for warning in caught if warning.category is ResourceWarning]
        self.assertEqual(resource_warnings, [])

    def test_add_product(self):
        self.assertEqual(database.add_product("Ballpen (Black)", "School Supplies", 120, 8.5), "created")
        products = database.get_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["product_name"], "Ballpen (Black)")
        self.assertEqual(products[0]["quantity"], 120)

    def test_same_product_adds_to_stock(self):
        database.add_product("Ballpen (Black)", "School Supplies", 120, 8.5)
        self.assertEqual(database.add_product("ballpen (black)", "School Supplies", 10, 8.50), "restocked")
        products = database.get_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["quantity"], 130)

    def test_restock_cannot_go_over_the_limit(self):
        database.add_product("Paper Clip", "School Supplies", database.MAX_QUANTITY, 1)
        self.assertEqual(database.add_product("Paper Clip", "School Supplies", 1, 1), "too_much")
        self.assertEqual(database.get_products()[0]["quantity"], database.MAX_QUANTITY)

    def test_update_product(self):
        database.add_product("Iced Tea 1L", "Drinks", 8, 45)
        product_id = database.get_products()[0]["product_id"]
        self.assertEqual(database.update_product(product_id, "Iced Tea 1L", "Drinks", 40, 45), "updated")
        self.assertEqual(database.get_products()[0]["quantity"], 40)

    def test_update_cannot_make_a_duplicate(self):
        database.add_product("Pen", "School Supplies", 10, 12)
        database.add_product("Pencil", "School Supplies", 5, 12)
        pencil_id = database.get_products()[0]["product_id"]
        self.assertEqual(database.update_product(pencil_id, "Pen", "School Supplies", 5, 12), "duplicate")
        names = sorted(p["product_name"] for p in database.get_products())
        self.assertEqual(names, ["Pen", "Pencil"])

    def test_delete_product(self):
        database.add_product("Floor Mop", "Cleaning", 3, 150)
        product_id = database.get_products()[0]["product_id"]
        database.delete_product(product_id)
        self.assertEqual(database.get_products(), [])

    def test_dashboard_totals(self):
        database.add_product("Ballpen (Black)", "School Supplies", 120, 8.5)
        database.add_product("Iced Tea 1L", "Drinks", 8, 45)
        database.add_product("Floor Mop", "Cleaning", 0, 150)
        totals = database.get_dashboard_totals()
        self.assertEqual(totals["total_products"], 3)
        self.assertEqual(totals["total_stock_units"], 128)
        self.assertEqual(totals["low_stock_products"], 2)
        self.assertAlmostEqual(totals["total_value"], 120 * 8.5 + 8 * 45)


    def test_update_missing_product(self):
        self.assertEqual(database.update_product(999, "Ghost", "Other", 1, 1), "missing")

    def test_delete_missing_product(self):
        self.assertEqual(database.delete_product(999), "missing")

    def test_tables_are_created(self):
        with database.database_connection() as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"products", "users", "registration_requests", "activity_log", "login_attempts"} <= names)

    def test_csv_export_escapes_spreadsheet_formulas(self):
        for dangerous in ("=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "\tformula", "\rformula"):
            self.assertEqual(database_viewer.csv_safe(dangerous), "'" + dangerous)
        self.assertEqual(database_viewer.csv_safe("ordinary text"), "ordinary text")

    def test_database_viewer_exposes_five_safe_views(self):
        self.assertEqual(
            set(database_viewer.TABLES),
            {"products", "users", "registration_requests", "login_attempts", "activity_log"},
        )
        for table in database_viewer.TABLES.values():
            self.assertNotIn("password_hash", table["columns"])
            self.assertNotIn("photo", table["columns"])


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.real_path = database.DB_PATH
        database.DB_PATH = Path(self.folder.name) / "test_inventory.db"
        database.initialize_database()
        auth._failed_attempts.clear()

    def tearDown(self):
        database.DB_PATH = self.real_path
        self.folder.cleanup()

    def test_password_is_hashed_with_salt(self):
        first = auth.hash_password("secret123")
        second = auth.hash_password("secret123")
        self.assertNotEqual(first, second)  # different random salt each time
        self.assertNotIn("secret123", first)
        self.assertTrue(first.startswith("pbkdf2_sha256$"))
        self.assertTrue(auth.verify_password("secret123", first))
        self.assertFalse(auth.verify_password("Secret123", first))
        self.assertFalse(auth.verify_password("secret123", "not a hash"))
        self.assertFalse(auth.verify_password("secret123", "pbkdf2_sha256$999999999$00$00"))

    def test_sign_up_and_sign_in(self):
        user = auth.sign_up("Juan Dela Cruz", "juan_dc", "inventory1", "inventory1")
        self.assertEqual(user.initials, "JC")
        stored = database.get_user_by_username("JUAN_DC")
        self.assertNotIn("inventory1", stored["password_hash"])

        self.assertIsNone(stored["last_login"])  # signing up does not sign in

        signed_in = auth.sign_in("Juan_DC", "inventory1")
        self.assertEqual(signed_in.user_id, user.user_id)
        self.assertEqual(signed_in.full_name, "Juan Dela Cruz")
        self.assertIsNotNone(database.get_user_by_username("juan_dc")["last_login"])

    def test_username_must_be_unique(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        with self.assertRaises(ValidationError) as caught:
            auth.admin_create_user(admin, "Another Juan", "JUAN", "inventory2", "inventory2", "staff")
        self.assertEqual(caught.exception.field, "username")
        self.assertEqual(database.count_users(), 1)

    def test_wrong_password_and_unknown_user(self):
        auth.sign_up("Maria Santos", "maria", "inventory1", "inventory1")
        for username in ("maria", "nobody"):
            with self.assertRaises(ValidationError) as caught:
                auth.sign_in(username, "wrongpass1")
            self.assertIn("Wrong username or password", caught.exception.message)

    def test_lockout_after_too_many_attempts(self):
        auth.sign_up("Maria Santos", "maria", "inventory1", "inventory1")
        for _ in range(auth.MAX_FAILED_ATTEMPTS):
            with self.assertRaises(ValidationError):
                auth.sign_in("maria", "wrongpass1")
        with self.assertRaises(ValidationError) as caught:
            auth.sign_in("maria", "inventory1")  # even the right password waits during the lockout
        self.assertIn("wait", caught.exception.message)
        auth._failed_attempts.clear()  # restarting the UI cannot bypass the database lockout
        self.assertGreater(auth.seconds_locked("maria"), 0)

    def test_activity_is_saved_with_the_user(self):
        user = auth.sign_up("Maria Santos", "maria", "inventory1", "inventory1")
        database.add_activity(user.user_id, "ADD", "Added Pen.")
        rows = database.get_recent_activity()
        self.assertEqual([row["action"] for row in rows], ["SIGN UP", "ADD"])
        self.assertEqual(rows[-1]["username"], "maria")


    def test_products_remember_who_changed_them(self):
        juan = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        maria = auth.admin_create_user(juan, "Maria Santos", "maria", "inventory2", "inventory2", "staff")
        database.add_product("Pen", "School Supplies", 10, 12, user_id=juan.user_id)
        product = database.get_products()[0]
        self.assertEqual(product["created_by_name"], "juan")
        self.assertEqual(product["updated_by_name"], "juan")
        database.update_product(product["product_id"], "Pen", "School Supplies", 20, 12, user_id=maria.user_id)
        product = database.get_products()[0]
        self.assertEqual(product["created_by_name"], "juan")
        self.assertEqual(product["updated_by_name"], "maria")
        self.assertIsNotNone(product["updated_at"])

    def test_profile_stats_and_team(self):
        juan = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        auth.admin_create_user(juan, "Maria Santos", "maria", "inventory2", "inventory2", "staff")
        for action in ("ADD", "ADD", "UPDATE", "RESTOCK", "DELETE"):
            database.add_activity(juan.user_id, action, "test")
        stats = database.get_user_stats(juan.user_id)
        self.assertEqual((stats["ADD"], stats["UPDATE"], stats["RESTOCK"], stats["DELETE"], stats["total"]), (2, 1, 1, 1, 5))
        self.assertIsNotNone(stats["last_change"])
        team = database.get_team_summary()
        self.assertEqual([(m["username"], m["changes"]) for m in team], [("juan", 5), ("maria", 0)])
        actions = [row["action"] for row in database.get_user_activity(juan.user_id)]
        self.assertEqual(actions[0], "DELETE")  # newest first
        self.assertIn("SIGN UP", actions)

    def test_change_name_and_password(self):
        user = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        renamed = auth.change_full_name(user, "  Juan  P. Dela Cruz ")
        self.assertEqual(renamed.full_name, "Juan P. Dela Cruz")
        self.assertEqual(database.get_user_by_id(user.user_id)["full_name"], "Juan P. Dela Cruz")

        cases = [
            (("wrongpass1", "newpass123", "newpass123"), "current"),
            (("inventory1", "short1", "short1"), "new"),
            (("inventory1", "inventory1", "inventory1"), "new"),
            (("inventory1", "newpass123", "newpass124"), "confirm"),
        ]
        for values, field in cases:
            with self.assertRaises(ValidationError) as caught:
                auth.change_password(renamed, *values)
            self.assertEqual(caught.exception.field, field, values)

        auth.change_password(renamed, "inventory1", "newpass123", "newpass123")
        with self.assertRaises(ValidationError):
            auth.sign_in("juan", "inventory1")
        self.assertEqual(auth.sign_in("juan", "newpass123").full_name, "Juan P. Dela Cruz")

    def test_old_database_is_upgraded(self):
        old_path = Path(self.folder.name) / "old.db"
        connection = sqlite3.connect(old_path)
        connection.execute(
            "CREATE TABLE products (product_id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL, "
            "category TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL)"
        )
        connection.execute("INSERT INTO products (product_name, category, quantity, unit_price) VALUES ('Pen', 'School Supplies', 5, 12)")
        connection.commit()
        connection.close()
        database.DB_PATH = old_path
        database.initialize_database()
        product = database.get_products()[0]
        self.assertEqual(product["product_name"], "Pen")
        self.assertIsNone(product["updated_by_name"])
        self.assertEqual(database.count_users(), 0)


    def test_first_account_is_admin_and_others_are_staff(self):
        first = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        second = auth.admin_create_user(first, "Maria Santos", "maria", "inventory2", "inventory2", "staff")
        self.assertTrue(first.is_admin)
        self.assertFalse(second.is_admin)
        self.assertEqual(auth.sign_in("maria", "inventory2").role, "staff")
        self.assertEqual(auth.sign_in("juan", "inventory1").role, "admin")

    def test_login_portals_require_the_matching_role(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        staff = auth.admin_create_user(admin, "Maria Santos", "maria", "inventory2", "inventory2", "staff")

        self.assertEqual(auth.sign_in("juan", "inventory1", required_role="admin"), admin)
        self.assertEqual(auth.sign_in("maria", "inventory2", required_role="staff"), staff)
        with self.assertRaises(ValidationError) as caught:
            auth.sign_in("maria", "inventory2", required_role="admin")
        self.assertIn("Administrator account required", caught.exception.message)
        with self.assertRaises(ValidationError) as caught:
            auth.sign_in("juan", "inventory1", required_role="staff")
        self.assertIn("Staff account required", caught.exception.message)

    def test_registration_requires_admin_approval(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        request_id = auth.request_account("Maria Santos", "maria", "inventory2", "inventory2", "admin")

        self.assertEqual(database.count_users(), 1)
        self.assertEqual(database.get_pending_registration_requests()[0]["request_id"], request_id)
        with database.database_connection() as connection:
            pending_hash = connection.execute(
                "SELECT password_hash FROM registration_requests WHERE request_id = ?", (request_id,)
            ).fetchone()["password_hash"]
        self.assertNotIn("inventory2", pending_hash)
        with self.assertRaises(ValidationError):
            auth.sign_in("maria", "inventory2")

        approved = auth.admin_approve_registration(admin, request_id, "staff")
        self.assertEqual(approved.role, "staff")
        self.assertEqual(auth.sign_in("maria", "inventory2", required_role="staff").user_id, approved.user_id)
        self.assertEqual(database.get_pending_registration_requests(), [])
        with database.database_connection() as connection:
            saved = connection.execute(
                "SELECT status, password_hash FROM registration_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
        self.assertEqual((saved["status"], saved["password_hash"]), ("approved", ""))

    def test_rejected_registration_cannot_sign_in(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        request_id = auth.request_account("Maria Santos", "maria", "inventory2", "inventory2", "staff")
        auth.admin_reject_registration(admin, request_id)

        with self.assertRaises(ValidationError):
            auth.sign_in("maria", "inventory2")
        with database.database_connection() as connection:
            saved = connection.execute(
                "SELECT status, password_hash FROM registration_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
        self.assertEqual((saved["status"], saved["password_hash"]), ("rejected", ""))

    def test_rbac_uses_current_saved_role(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        staff = auth.admin_create_user(admin, "Maria Santos", "maria", "inventory2", "inventory2", "staff")
        forged_admin = auth.User(staff.user_id, staff.username, staff.full_name, role="admin")
        request_id = auth.request_account("Pedro Cruz", "pedro", "inventory3", "inventory3", "admin")

        self.assertIsNotNone(auth.require_permission(staff, "edit_products"))
        with self.assertRaises(ValidationError):
            auth.admin_create_user(forged_admin, "Pedro Cruz", "pedro", "inventory3", "inventory3", "admin")
        self.assertEqual(database.approve_registration_request(request_id, staff.user_id, "admin"), "forbidden")
        self.assertTrue(database.pending_registration_exists("pedro"))
        auth.admin_set_active(admin, staff.user_id, False)
        with self.assertRaises(ValidationError):
            auth.require_permission(staff, "edit_products")
        with self.assertRaises(ValidationError):
            auth.sign_up("Another User", "another", "inventory4", "inventory4")
        self.assertEqual(database.add_product("Pen", "Other", 1, 1, user_id=staff.user_id), "forbidden")
        self.assertEqual(database.delete_product(999, user_id=staff.user_id), "forbidden")
        with self.assertRaises(ValidationError):
            auth.change_full_name(staff, "Inactive Staff")

    def test_admin_tools(self):
        admin = auth.sign_up("Juan Dela Cruz", "juan", "inventory1", "inventory1")
        staff = auth.admin_create_user(admin, "Maria Santos", "maria", "inventory2", "inventory2", "staff")

        with self.assertRaises(ValidationError):
            auth.admin_set_active(staff, admin.user_id, False)  # staff cannot use admin tools
        with self.assertRaises(ValidationError):
            auth.admin_set_role(admin, admin.user_id, "staff")  # the last admin must stay
        with self.assertRaises(ValidationError):
            auth.admin_set_active(admin, admin.user_id, False)  # cannot deactivate yourself

        auth.admin_set_active(admin, staff.user_id, False)
        with self.assertRaises(ValidationError) as caught:
            auth.sign_in("maria", "inventory2")
        self.assertIn("inactive", caught.exception.message)
        auth.admin_set_active(admin, staff.user_id, True)

        temporary = auth.admin_reset_password(admin, staff.user_id)
        self.assertGreaterEqual(len(temporary), 16)
        self.assertTrue(database.get_user_by_id(staff.user_id)["must_change_password"])
        with self.assertRaises(ValidationError):
            auth.sign_in("maria", "inventory2")
        reset_user = auth.sign_in("maria", temporary)
        self.assertEqual(reset_user.username, "maria")
        self.assertTrue(reset_user.must_change_password)
        with self.assertRaises(ValidationError):
            auth.require_permission(reset_user, "edit_products")
        reset_user = auth.change_password(reset_user, temporary, "replacement9", "replacement9")
        self.assertFalse(reset_user.must_change_password)
        self.assertIsNotNone(auth.require_permission(reset_user, "edit_products"))

        auth.admin_set_role(admin, staff.user_id, "admin")
        self.assertEqual(database.get_user_by_id(staff.user_id)["role"], "admin")
        auth.admin_set_role(admin, admin.user_id, "staff")  # allowed now that there is another admin
        actions = [row["action"] for row in database.get_all_activity(50)]
        self.assertIn("ROLE", actions)
        self.assertIn("ACCOUNT", actions)

    def test_old_users_table_gets_roles(self):
        old_path = Path(self.folder.name) / "old_users.db"
        connection = sqlite3.connect(old_path)
        connection.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, "
            "full_name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL, last_login TEXT)"
        )
        for name in ("first", "second"):
            connection.execute(
                "INSERT INTO users (username, full_name, password_hash, created_at) VALUES (?, ?, ?, '2026-11-16 08:00:00')",
                (name, name.title(), auth.hash_password("inventory1")),
            )
        connection.commit()
        connection.close()
        database.DB_PATH = old_path
        database.initialize_database()
        self.assertEqual(auth.sign_in("first", "inventory1").role, "admin")
        self.assertEqual(auth.sign_in("second", "inventory1").role, "staff")


# The smallest real PNG picture: one transparent pixel.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4b00000000049454e44ae426082"
)


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.real_path = database.DB_PATH
        database.DB_PATH = Path(self.folder.name) / "test_inventory.db"
        database.initialize_database()
        self.user = auth.sign_up("Maria Santos", "maria", "inventory1", "inventory1")

    def tearDown(self):
        database.DB_PATH = self.real_path
        self.folder.cleanup()

    def picture(self, name, data):
        path = Path(self.folder.name) / name
        path.write_bytes(data)
        return path

    def test_change_and_remove_photo(self):
        self.assertIsNone(database.get_photo(self.user.user_id))
        auth.change_photo(self.user, self.picture("me.png", TINY_PNG))
        self.assertEqual(database.get_photo(self.user.user_id), TINY_PNG)
        auth.remove_photo(self.user)
        self.assertIsNone(database.get_photo(self.user.user_id))
        details = [row["details"] for row in database.get_user_activity(self.user.user_id)]
        self.assertIn("Changed profile photo.", details)
        self.assertIn("Removed profile photo.", details)

    def test_gif_is_allowed(self):
        gif = bytes.fromhex(
            "47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b"
        )
        auth.change_photo(self.user, self.picture("me.gif", gif))
        self.assertTrue(database.get_photo(self.user.user_id).startswith(b"GIF89a"))

    def test_wrong_type_is_refused(self):
        jpeg_start = bytes.fromhex("ffd8ffe0")
        for name, data in (("me.jpg", jpeg_start + bytes(20)), ("notes.txt", b"hello")):
            with self.assertRaises(ValidationError) as caught:
                auth.change_photo(self.user, self.picture(name, data))
            self.assertIn("PNG or GIF", caught.exception.message)
        self.assertIsNone(database.get_photo(self.user.user_id))

    def test_too_big_is_refused(self):
        big = TINY_PNG + b"\x00" * (auth.MAX_PHOTO_BYTES + 1)
        with self.assertRaises(ValidationError) as caught:
            auth.change_photo(self.user, self.picture("big.png", big))
        self.assertIn("too big", caught.exception.message)

    def test_old_database_gets_photo_column(self):
        database.DB_PATH = Path(self.folder.name) / "old.db"
        with database.database_connection() as connection:
            connection.execute(
                "CREATE TABLE users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, "
                "full_name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL, last_login TEXT)"
            )
            connection.execute("INSERT INTO users (username, full_name, password_hash, created_at) VALUES ('old', 'Old User', 'x', '2026-01-01')")
        database.initialize_database()
        with database.database_connection() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        self.assertIn("photo", columns)
        self.assertIsNone(database.get_photo(1))


class InputCheckTests(unittest.TestCase):
    def test_good_quantities(self):
        self.assertEqual(parse_quantity("25"), 25)
        self.assertEqual(parse_quantity(" 0 "), 0)

    def test_bad_quantities(self):
        for text in ("abc", "2.5", "1e3", "1_000", "", "١٢"):
            self.assertIsNone(parse_quantity(text), text)

    def test_good_prices(self):
        self.assertEqual(parse_price("25"), 25)
        self.assertEqual(parse_price("8.50"), 8.5)
        self.assertEqual(parse_price(".75"), 0.75)

    def test_bad_prices(self):
        for text in ("abc", "inf", "nan", "1e3", "1_000", "8.555", ""):
            self.assertIsNone(parse_price(text), text)


    def test_product_form_checks(self):
        self.assertEqual(validate_product("  Ballpen   Black ", "School Supplies", "5", "8.50"), ("Ballpen Black", "School Supplies", 5, 8.5))
        cases = [
            (("", "Food", "1", "1"), "name"),
            (("x" * 61, "Food", "1", "1"), "name"),
            (("Pen", " ", "1", "1"), "category"),
            (("Pen", "Food", "", "1"), "quantity"),
            (("Pen", "Food", "-1", "1"), "quantity"),
            (("Pen", "Food", "2000000", "1"), "quantity"),
            (("Pen", "Food", "1", ""), "price"),
            (("Pen", "Food", "1", "-5"), "price"),
            (("Pen", "Food", "1", "2000000"), "price"),
        ]
        for values, field in cases:
            with self.assertRaises(ValidationError) as caught:
                validate_product(*values)
            self.assertEqual(caught.exception.field, field, values)

    def test_sign_up_checks(self):
        cases = [
            (("", "juan", "inventory1", "inventory1"), "full_name"),
            (("Juan", "ju", "inventory1", "inventory1"), "username"),
            (("Juan", "juan dc", "inventory1", "inventory1"), "username"),
            (("Juan", "juan", "short1", "short1"), "password"),
            (("Juan", "juan", "lettersonly", "lettersonly"), "password"),
            (("Juan", "juan", "12345678", "12345678"), "password"),
            (("Juan", "juan", "inventory1", "inventory2"), "confirm"),
        ]
        for values, field in cases:
            with self.assertRaises(ValidationError) as caught:
                validate_sign_up(*values)
            self.assertEqual(caught.exception.field, field, values)


if __name__ == "__main__":
    unittest.main()
