import csv
import sqlite3
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import database
import theme
from theme import COLORS, FlatButton


DB_PATH = database.DB_PATH
COLUMNS = ("product_id", "product_name", "category", "quantity", "unit_price")
SELECT = "SELECT * FROM products"

# Ready-made, read-only queries. Users pick one; they cannot type their own SQL.
QUERIES = {
    "All rows": (f"{SELECT} ORDER BY product_id DESC", ()),
    f"Low stock (below {database.LOW_STOCK_THRESHOLD})": (
        f"{SELECT} WHERE quantity < ? ORDER BY quantity",
        (database.LOW_STOCK_THRESHOLD,),
    ),
    "Sort by price": (f"{SELECT} ORDER BY unit_price DESC", ()),
}


def sans(size, weight="normal"):
    return (theme.FONT, size, weight)


def code(size, weight="normal"):
    return (theme.CODE, size, weight)


class DatabaseViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Records - inventory.db")
        self.root.geometry("1100x680")
        self.root.minsize(900, 560)

        theme.load_fonts(self.root)
        theme.apply_ttk_theme(self.root)

        self.query_name = "All rows"
        self.records = []
        self.preset_buttons = {}

        self.sql_var = tk.StringVar()
        self.table_title_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.info_vars = {name: tk.StringVar(value="--") for name in ("SQLite version", "Journal mode", "File size", "Total rows", "Integrity check")}

        self.build_screen()
        self.load_records()

    # ------------------------------------------------------------------ layout

    def panel(self, parent, padx=16, pady=12):
        outer = tk.Frame(parent, bg=COLORS["line"])
        inner = tk.Frame(outer, bg=COLORS["card"], padx=padx, pady=pady)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def build_screen(self):
        self.build_header()

        body = tk.Frame(self.root, bg=COLORS["page"], padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        self.build_info_strip(body)
        self.build_query_bar(body)
        self.build_bottom_row(body)
        self.build_table(body)

    def build_header(self):
        header = tk.Frame(self.root, bg=COLORS["header"], padx=20, pady=12)
        header.pack(fill=tk.X)
        tk.Frame(self.root, bg=COLORS["line"], height=1).pack(fill=tk.X)

        left = tk.Frame(header, bg=COLORS["header"])
        left.pack(side=tk.LEFT)
        tk.Label(left, text="products table", bg=COLORS["primary_soft"], fg=COLORS["primary"], font=sans(8, "bold"), padx=6).pack(anchor=tk.W)
        line = tk.Frame(left, bg=COLORS["header"])
        line.pack(anchor=tk.W, pady=(4, 0))
        tk.Label(line, text="Database Records", bg=COLORS["header"], fg=COLORS["strong"], font=sans(16, "bold")).pack(side=tk.LEFT)
        tk.Label(line, text=f"  —  {DB_PATH.name}", bg=COLORS["header"], fg=COLORS["muted"], font=sans(12)).pack(side=tk.LEFT, pady=(3, 0))
        tk.Label(
            left, text="The rows exactly as they are saved in the database file.", bg=COLORS["header"], fg=COLORS["muted"], font=sans(9)
        ).pack(anchor=tk.W)

        FlatButton(
            header, "Refresh Database", self.load_records, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=9, pady=7, border=COLORS["button"],
        ).pack(side=tk.RIGHT)
        FlatButton(
            header, "Export CSV", self.export_csv, COLORS["card_high"], COLORS["text"], COLORS["card_top"],
            font_size=9, pady=7, border=COLORS["line_high"], hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def build_info_strip(self, parent):
        strip = tk.Frame(parent, bg=COLORS["page"])
        strip.pack(fill=tk.X)
        for index, (name, variable) in enumerate(self.info_vars.items()):
            strip.columnconfigure(index, weight=1, uniform="info")
            outer, tile = self.panel(strip, padx=12, pady=8)
            outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            tk.Label(tile, text=name, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8)).pack(anchor=tk.W)
            label = tk.Label(tile, textvariable=variable, bg=COLORS["card"], fg=COLORS["strong"], font=sans(11, "bold"))
            label.pack(anchor=tk.W)
            if name == "Integrity check":
                self.integrity_label = label

    def build_query_bar(self, parent):
        bar = tk.Frame(parent, bg=COLORS["input"], padx=12, pady=7, highlightthickness=1, highlightbackground=COLORS["line_high"])
        bar.pack(fill=tk.X, pady=(12, 0))
        tk.Label(bar, text="SQL", bg=COLORS["input"], fg=COLORS["primary"], font=sans(9, "bold")).pack(side=tk.LEFT)
        tk.Label(bar, textvariable=self.sql_var, bg=COLORS["input"], fg=COLORS["text"], font=code(9), anchor=tk.W).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10)
        )

    def build_presets(self, parent):
        tk.Label(parent, text="Quick queries:", bg=COLORS["card"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT, padx=(16, 2))
        for name in QUERIES:
            button = FlatButton(
                parent, name, lambda value=name: self.run_preset(value), COLORS["card_high"], COLORS["dim"], COLORS["card_top"],
                font_size=8, padx=9, pady=3, border=COLORS["line"], hover_fg=COLORS["strong"], weight="normal",
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self.preset_buttons[name] = button

    def build_table(self, parent):
        outer, card = self.panel(parent, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        top = tk.Frame(card, bg=COLORS["card"], padx=16, pady=9)
        top.pack(fill=tk.X)
        tk.Label(top, textvariable=self.table_title_var, bg=COLORS["card"], fg=COLORS["strong"], font=sans(11, "bold")).pack(side=tk.LEFT)
        self.build_presets(top)

        table_area = tk.Frame(card, bg=COLORS["card"])
        table_area.pack(fill=tk.BOTH, expand=True)
        table_area.rowconfigure(0, weight=1)
        table_area.columnconfigure(0, weight=1)

        types = self.column_types()
        widths = {"product_id": 130, "product_name": 260, "category": 170, "quantity": 130, "unit_price": 140}
        anchors = {"product_id": tk.W, "quantity": tk.E, "unit_price": tk.E}
        self.tree = ttk.Treeview(table_area, columns=COLUMNS, show="headings", selectmode="browse", height=5)
        for column in COLUMNS:
            anchor = anchors.get(column, tk.W)
            self.tree.heading(column, text=f"{column}  ({types.get(column, '')})", anchor=anchor)
            self.tree.column(column, width=widths[column], minwidth=80, anchor=anchor)

        self.tree.tag_configure("even", background=COLORS["card"])
        self.tree.tag_configure("odd", background=COLORS["row_alt"])

        scrollbar = ttk.Scrollbar(table_area, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = tk.Frame(card, bg=COLORS["card_high"], padx=16, pady=5)
        footer.pack(fill=tk.X)
        tk.Label(footer, textvariable=self.status_var, bg=COLORS["card_high"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT)

    def build_bottom_row(self, parent):
        row = tk.Frame(parent, bg=COLORS["page"], height=172)
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
        row.grid_propagate(False)
        row.columnconfigure(0, weight=1, uniform="bottom")
        row.columnconfigure(1, weight=1, uniform="bottom")
        row.rowconfigure(0, weight=1)

        outer, schema = self.panel(row)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(schema, text="Table Schema", bg=COLORS["card"], fg=COLORS["primary"], font=sans(9, "bold")).pack(anchor=tk.W)
        self.schema_box = self.text_box(schema)

        outer, console = self.panel(row)
        outer.grid(row=0, column=1, sticky="nsew")
        top = tk.Frame(console, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text="Query Log", bg=COLORS["card"], fg=COLORS["primary"], font=sans(9, "bold")).pack(side=tk.LEFT)
        tk.Label(top, text="Queries run in this window", bg=COLORS["card"], fg=COLORS["faint"], font=sans(8)).pack(side=tk.RIGHT)
        self.log_box = self.text_box(console)
        self.log_box.tag_configure("time", foreground=COLORS["faint"])
        self.log_box.tag_configure("ok", foreground=COLORS["primary"])

    def text_box(self, parent):
        box = tk.Text(
            parent, height=4, bg=COLORS["card"], fg=COLORS["dim"], font=code(9), relief=tk.FLAT, bd=0,
            highlightthickness=0, padx=0, pady=6, wrap=tk.WORD, cursor="arrow",
        )
        box.pack(fill=tk.BOTH, expand=True)
        box.configure(state=tk.DISABLED)
        return box

    # ------------------------------------------------------------------ data

    def column_types(self):
        with database.database_connection() as connection:
            info = connection.execute("PRAGMA table_info(products)").fetchall()
        return {name: f"{kind} PK" if primary_key else kind for _, name, kind, _, _, primary_key in info}

    def run_preset(self, name):
        self.query_name = name
        self.load_records()

    def load_records(self):
        sql, parameters = QUERIES[self.query_name]
        started = time.perf_counter()
        with database.database_connection() as connection:
            self.records = connection.execute(sql, parameters).fetchall()
            total_rows = connection.execute("SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM products").fetchone()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            schema = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'products'").fetchone()
        fetch_ms = (time.perf_counter() - started) * 1000

        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, record in enumerate(self.records):
            product_id, name, category, quantity, unit_price = record
            self.tree.insert(
                "", tk.END, values=(product_id, name, category, quantity, f"{unit_price:.2f}"),
                tags=("even" if index % 2 == 0 else "odd",),
            )

        shown_sql = sql.replace("?", str(parameters[0])) if parameters else sql
        self.sql_var.set(f"{shown_sql};")
        for name, button in self.preset_buttons.items():
            active = name == self.query_name
            button.colors = (
                COLORS["primary_soft"] if active else COLORS["card_high"],
                COLORS["primary"] if active else COLORS["dim"],
                COLORS["card_top"],
                COLORS["strong"],
            )
            button.configure(bg=button.colors[0], fg=button.colors[1])

        count = len(self.records)
        self.table_title_var.set(f"Table: products  ({count} row{'s' if count != 1 else ''} returned)")
        self.status_var.set(
            f"{total_rows[0]} product record(s)  ·  Read directly from {DB_PATH.name}  ·  "
            f"Updates by itself after every change  ·  Fetch time {fetch_ms:.1f} ms"
        )

        size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        self.info_vars["SQLite version"].set(sqlite3.sqlite_version)
        self.info_vars["Journal mode"].set(str(journal_mode).upper())
        self.info_vars["File size"].set(f"{size / 1024:,.1f} KB")
        self.info_vars["Total rows"].set(f"{total_rows[0]} rows  ·  {total_rows[1]:,} units")
        self.info_vars["Integrity check"].set("OK" if integrity == "ok" else str(integrity))
        self.integrity_label.configure(fg=COLORS["primary"] if integrity == "ok" else COLORS["red"])

        ddl = schema[0].replace("(", "(\n    ", 1).replace(", ", ",\n    ") if schema else "No products table yet."
        self.set_text(self.schema_box, ddl.rstrip(")") + "\n);" if schema else ddl)
        self.add_log(f"{shown_sql};", f"{count} row(s) in {fetch_ms:.1f} ms")

    def set_text(self, box, text):
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        box.insert(tk.END, text)
        box.configure(state=tk.DISABLED)

    def add_log(self, sql, result):
        box = self.log_box
        box.configure(state=tk.NORMAL)
        if box.index("end-1c") != "1.0":
            box.insert(tk.END, "\n")
        box.insert(tk.END, datetime.now().strftime("%H:%M:%S") + "  ", "time")
        box.insert(tk.END, sql + "  ")
        box.insert(tk.END, f"→ {result}", "ok")
        box.see(tk.END)
        box.configure(state=tk.DISABLED)

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export products to CSV",
            defaultextension=".csv",
            initialfile=f"products_{datetime.now():%Y-%m-%d}.csv",
            filetypes=[("CSV file", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(COLUMNS)
                writer.writerows(self.records)
        except OSError as error:
            messagebox.showerror("Export failed", f"The file could not be saved.\n\n{error}", parent=self.root)
            return
        self.add_log(f"Exported {len(self.records)} row(s) to CSV", path)


def main():
    database.initialize_database()
    root = tk.Tk()
    DatabaseViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
