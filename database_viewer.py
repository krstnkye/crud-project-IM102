import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk


DB_PATH = Path(__file__).with_name("inventory.db")


class DatabaseViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Records - inventory.db")
        self.root.geometry("920x520")
        self.root.minsize(760, 420)
        self.root.configure(bg="#f8f9ff")

        self.status_var = tk.StringVar()
        self.build_screen()
        self.load_records()

    def build_screen(self):
        heading = tk.Frame(self.root, bg="#213145", padx=18, pady=14)
        heading.pack(fill=tk.X)

        tk.Label(
            heading,
            text="Database Records",
            bg="#213145",
            fg="#ffffff",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            heading,
            text=str(DB_PATH),
            bg="#213145",
            fg="#dce7f5",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W, pady=(3, 0))

        toolbar = tk.Frame(self.root, bg="#f8f9ff", padx=18, pady=14)
        toolbar.pack(fill=tk.X)

        tk.Label(
            toolbar,
            text="Table: products",
            bg="#f8f9ff",
            fg="#0b1c30",
            font=("Segoe UI", 12, "bold"),
        ).pack(side=tk.LEFT)

        tk.Button(
            toolbar,
            text="Refresh Database",
            command=self.load_records,
            bg="#004ac6",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        table_frame = tk.Frame(self.root, bg="#ffffff", padx=18, pady=4)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        columns = ("product_id", "product_name", "category", "quantity", "unit_price")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("product_id", text="product_id")
        self.tree.heading("product_name", text="product_name")
        self.tree.heading("category", text="category")
        self.tree.heading("quantity", text="quantity")
        self.tree.heading("unit_price", text="unit_price")

        self.tree.column("product_id", width=100, anchor=tk.CENTER)
        self.tree.column("product_name", width=250)
        self.tree.column("category", width=180)
        self.tree.column("quantity", width=110, anchor=tk.CENTER)
        self.tree.column("unit_price", width=150, anchor=tk.E)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#eef3fb",
            fg="#334155",
            font=("Segoe UI", 9),
            anchor=tk.W,
            padx=18,
            pady=10,
        ).pack(fill=tk.X)

    def load_records(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        with sqlite3.connect(DB_PATH) as connection:
            records = connection.execute(
                """
                SELECT product_id, product_name, category, quantity, unit_price
                FROM products
                ORDER BY product_id DESC
                """
            ).fetchall()

        for record in records:
            self.tree.insert("", tk.END, values=record)

        self.status_var.set(
            f"{len(records)} product record(s). This window reads directly from inventory.db."
        )


def main():
    root = tk.Tk()
    DatabaseViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
