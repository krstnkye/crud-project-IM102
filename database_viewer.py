import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import theme
from theme import COLORS, FlatButton


DB_PATH = Path(__file__).with_name("inventory.db")


class DatabaseViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Records - inventory.db")
        self.root.geometry("960x560")
        self.root.minsize(760, 420)

        theme.load_fonts(self.root)
        theme.apply_ttk_theme(self.root)

        self.status_var = tk.StringVar()
        self.build_screen()
        self.load_records()

    def build_screen(self):
        heading = tk.Frame(self.root, bg=COLORS["page"], padx=24, pady=20)
        heading.pack(fill=tk.X)

        left = tk.Frame(heading, bg=COLORS["page"])
        left.pack(side=tk.LEFT)
        tk.Label(
            left,
            text="DATABASE RECORDS",
            bg=COLORS["page"],
            fg=COLORS["text"],
            font=(theme.MONO, 16, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            left,
            text=str(DB_PATH),
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=(theme.MONO, 9, "normal"),
        ).pack(anchor=tk.W, pady=(3, 0))

        FlatButton(
            heading,
            "↻  REFRESH DATABASE",
            self.load_records,
            COLORS["button"],
            COLORS["button_text"],
            COLORS["primary"],
            hover_fg="#ffffff",
        ).pack(side=tk.RIGHT)

        outer = tk.Frame(self.root, bg=COLORS["line"])
        outer.pack(fill=tk.BOTH, expand=True, padx=24)
        table_frame = tk.Frame(outer, bg=COLORS["card"], padx=16, pady=16)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        table_frame.rowconfigure(1, weight=1)
        table_frame.columnconfigure(0, weight=1)

        tk.Label(
            table_frame,
            text="[TABLE: PRODUCTS]",
            bg=COLORS["card"],
            fg=COLORS["primary"],
            font=(theme.MONO, 9, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

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

        self.tree.tag_configure("even", background=COLORS["card"])
        self.tree.tag_configure("odd", background=COLORS["row_alt"])

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=(theme.MONO, 8),
            anchor=tk.W,
            padx=24,
            pady=14,
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

        for index, record in enumerate(records):
            self.tree.insert("", tk.END, values=record, tags=("even" if index % 2 == 0 else "odd",))

        self.status_var.set(
            f"●  {len(records)} product record(s). This window reads directly from inventory.db."
        )


def main():
    root = tk.Tk()
    DatabaseViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
