"""Automatic tests for the Product Inventory System.

Run them from the project folder with:

    python -m unittest test_database.py

The tests use a temporary database file, so your real inventory.db is not touched.
"""

import tempfile
import unittest
from pathlib import Path

import database
from main import parse_price, parse_quantity


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.real_path = database.DB_PATH
        database.DB_PATH = Path(self.folder.name) / "test_inventory.db"
        database.initialize_database()

    def tearDown(self):
        database.DB_PATH = self.real_path
        self.folder.cleanup()

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


if __name__ == "__main__":
    unittest.main()
