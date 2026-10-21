import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("inventory.db")
LOW_STOCK_THRESHOLD = 10


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
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


def add_product(product_name, category, quantity, unit_price):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO products (product_name, category, quantity, unit_price)
            VALUES (?, ?, ?, ?)
            """,
            (product_name, category, quantity, unit_price),
        )


def get_products():
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT product_id, product_name, category, quantity, unit_price
            FROM products
            ORDER BY product_id DESC
            """
        ).fetchall()


def update_product(product_id, product_name, category, quantity, unit_price):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET product_name = ?, category = ?, quantity = ?, unit_price = ?
            WHERE product_id = ?
            """,
            (product_name, category, quantity, unit_price, product_id),
        )


def delete_product(product_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM products WHERE product_id = ?",
            (product_id,),
        )


def get_dashboard_totals():
    with get_connection() as connection:
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
