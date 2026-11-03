import re
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import database
import theme
from theme import COLORS, FlatButton


CATEGORIES = ("School Supplies", "Food", "Drinks", "Cleaning", "Electronics", "Other")

# Table column -> (heading, width, anchor, key used for sorting)
TABLE_COLUMNS = {
    "product_id": ("ID", 64, tk.W, "product_id"),
    "product_name": ("Product", 210, tk.W, "product_name"),
    "category": ("Category", 130, tk.W, "category"),
    "quantity": ("Stock", 80, tk.E, "quantity"),
    "status": ("Status", 120, tk.W, "quantity"),
    "unit_price": ("Unit Price", 110, tk.E, "unit_price"),
    "total": ("Total Amount", 130, tk.E, "total"),
}

LOG_COLORS = {"BOOT": "primary", "ADD": "green", "RESTOCK": "green", "UPDATE": "primary", "DELETE": "red", "ALERT": "amber", "ERROR": "red", "THEME": "muted"}


QUANTITY_PATTERN = re.compile(r"-?\d+")
PRICE_PATTERN = re.compile(r"-?(\d+(\.\d{1,2})?|\.\d{1,2})")


def parse_quantity(text):
    """Return the quantity as a whole number, or None if it is not a plain whole number."""
    text = text.strip()
    return int(text) if QUANTITY_PATTERN.fullmatch(text) else None


def parse_price(text):
    """Return the price as a number with at most 2 decimal places, or None if it is not valid."""
    text = text.strip()
    return float(text) if PRICE_PATTERN.fullmatch(text) else None


def sans(size, weight="normal"):
    return (theme.FONT, size, weight)


def peso(amount):
    return f"PHP {amount:,.2f}"


def short_list(products):
    """Turn a list of products into a short line like "Floor Mop, Iced Tea 1L +2 more"."""
    names = [p["product_name"] for p in products[:2]]
    text = ", ".join(names)
    if len(products) > 2:
        text += f" +{len(products) - 2} more"
    return text if len(text) <= 38 else text[:37] + "…"


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Product Inventory System")
        self.root.geometry("1280x720")
        self.root.minsize(1100, 660)
        try:
            self.root.state("zoomed")  # open maximized on Windows
        except tk.TclError:
            pass

        self.selected_product_id = None
        self.products = []
        self.category_filter = "All"
        self.sort_key = "product_id"
        self.sort_reverse = True
        self.toast_job = None
        self.placeholder_trace = None
        self.log_entries = []
        self.viewer = None

        database.initialize_database()

        self.product_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value="School Supplies")
        self.quantity_var = tk.StringVar()
        self.unit_price_var = tk.StringVar()
        self.item_total_var = tk.StringVar(value=peso(0))
        self.search_var = tk.StringVar()
        self.error_var = tk.StringVar()
        self.row_count_var = tk.StringVar()

        self.total_value_var = tk.StringVar(value=peso(0))
        self.total_products_var = tk.StringVar(value="0")
        self.total_units_var = tk.StringVar(value="0 units")
        self.low_stock_var = tk.StringVar(value="0")
        self.low_stock_detail_var = tk.StringVar(value="All stock levels are OK")
        self.low_stock_unit_var = tk.StringVar(value=f"below {database.LOW_STOCK_THRESHOLD} pcs")
        self.out_stock_var = tk.StringVar(value="0")
        self.out_stock_detail_var = tk.StringVar(value="Nothing is out of stock")

        theme.load_fonts(self.root)
        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.bind_shortcuts()
        self.refresh_data()
        self.set_edit_mode(False)

        self.quantity_var.trace_add("write", self.update_item_total)
        self.unit_price_var.trace_add("write", self.update_item_total)
        self.search_var.trace_add("write", lambda *args: self.render_table())

        self.log("BOOT", f"Database ready. {len(self.products)} product(s) loaded from inventory.db.")
        low = [p for p in self.products if p["quantity"] < database.LOW_STOCK_THRESHOLD]
        if low:
            self.log("ALERT", f"{len(low)} product(s) below {database.LOW_STOCK_THRESHOLD} pieces. Restock suggested.")

    # ------------------------------------------------------------------ layout

    def build_interface(self):
        shell = tk.Frame(self.root, bg=COLORS["page"], padx=24, pady=18)
        shell.pack(fill=tk.BOTH, expand=True)

        self.build_header(shell)
        self.build_kpis(shell)
        self.build_footer(shell)

        main = tk.Frame(shell, bg=COLORS["page"])
        main.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=COLORS["page"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = tk.Frame(main, bg=COLORS["page"], width=340)
        right.grid(row=0, column=1, sticky="ns")
        right.pack_propagate(False)

        self.build_bottom_row(left)
        self.build_table(left)
        self.build_form(right)

        self.toast = tk.Frame(self.root, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["line"])
        self.toast_stripe = tk.Frame(self.toast, width=4, bg=COLORS["green"])
        self.toast_stripe.pack(side=tk.LEFT, fill=tk.Y)
        self.toast_label = tk.Label(self.toast, bg=COLORS["card"], fg=COLORS["strong"], font=sans(10), padx=14, pady=11)
        self.toast_label.pack(side=tk.LEFT)

    def panel(self, parent, padx=18, pady=16):
        """A white (or dark) card with a thin border."""
        outer = tk.Frame(parent, bg=COLORS["line"])
        inner = tk.Frame(outer, bg=COLORS["card"], padx=padx, pady=pady)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def section_title(self, parent, text, bg=None):
        return tk.Label(parent, text=text, bg=bg or COLORS["card"], fg=COLORS["strong"], font=sans(12, "bold"))

    def icon_badge(self, parent, icon, color, soft):
        return tk.Label(parent, text=icon, bg=soft, fg=color, font=sans(11, "bold"), width=3, pady=2)

    def build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["page"])
        header.pack(fill=tk.X)

        logo = tk.Canvas(header, width=42, height=42, bg=COLORS["page"], highlightthickness=0)
        logo.pack(side=tk.LEFT)
        logo.create_rectangle(0, 0, 42, 42, fill=COLORS["primary"], outline="")
        # a small box icon
        logo.create_polygon(21, 9, 33, 15, 21, 21, 9, 15, fill="#ffffff", outline="")
        logo.create_polygon(9, 18, 19, 23, 19, 34, 9, 29, fill="#ffffff", outline="")
        logo.create_polygon(33, 18, 23, 23, 23, 34, 33, 29, fill="#ffffff", outline="")

        names = tk.Frame(header, bg=COLORS["page"])
        names.pack(side=tk.LEFT, padx=(14, 0))
        tk.Label(names, text="Product Inventory", bg=COLORS["page"], fg=COLORS["strong"], font=sans(18, "bold")).pack(anchor=tk.W)
        tk.Label(
            names,
            text="IM102  ·  Keep track of your products, stock, and value",
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=sans(9),
        ).pack(anchor=tk.W)

        right = tk.Frame(header, bg=COLORS["page"])
        right.pack(side=tk.RIGHT)

        FlatButton(
            right,
            "+  New Product",
            self.start_new_product,
            COLORS["button"],
            COLORS["button_text"],
            COLORS["primary_hover"],
        ).pack(side=tk.RIGHT)

        FlatButton(
            right,
            "▤  DB Records",
            self.open_database_viewer,
            COLORS["card"],
            COLORS["text"],
            COLORS["card_high"],
            border=COLORS["line"],
            hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 10))

        toggle_text = "☀  Light Mode" if theme.MODE == "dark" else "☾  Dark Mode"
        FlatButton(
            right,
            toggle_text,
            self.toggle_theme,
            COLORS["card"],
            COLORS["text"],
            COLORS["card_high"],
            border=COLORS["line"],
            hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 10))

    def build_kpis(self, parent):
        strip = tk.Frame(parent, bg=COLORS["page"])
        strip.pack(fill=tk.X, pady=(16, 0))
        for column in range(4):
            strip.columnconfigure(column, weight=1, uniform="kpi")

        cards = [
            ("Total Inventory Value", "₱", "primary", self.total_value_var, None, "Quantity × unit price of all products"),
            ("Registered Products", "▦", "green", self.total_products_var, self.total_units_var, "Saved in inventory.db"),
            ("Low Stock Alert", "▲", "amber", self.low_stock_var, self.low_stock_unit_var, self.low_stock_detail_var),
            ("Out of Stock", "✕", "red", self.out_stock_var, None, self.out_stock_detail_var),
        ]

        for index, (title, icon, color, value, extra, note) in enumerate(cards):
            outer, card = self.panel(strip, padx=16, pady=11)
            outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 12, 0))

            top = tk.Frame(card, bg=COLORS["card"])
            top.pack(fill=tk.X)
            tk.Label(top, text=title, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9, "bold")).pack(side=tk.LEFT, anchor=tk.N)
            self.icon_badge(top, icon, COLORS[color], COLORS[f"{color}_soft"]).pack(side=tk.RIGHT)

            row = tk.Frame(card, bg=COLORS["card"])
            row.pack(fill=tk.X)
            tk.Label(row, textvariable=value, bg=COLORS["card"], fg=COLORS["strong"], font=sans(18, "bold")).pack(side=tk.LEFT)
            if extra is not None:
                tk.Label(row, textvariable=extra, bg=COLORS["card"], fg=COLORS["muted"], font=sans(10)).pack(side=tk.LEFT, padx=(8, 0), pady=(9, 0))

            note_options = {"textvariable": note} if isinstance(note, tk.StringVar) else {"text": note}
            tk.Label(card, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), anchor=tk.W, **note_options).pack(fill=tk.X, pady=(2, 0))

    def build_table(self, parent):
        outer, card = self.panel(parent, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(card, bg=COLORS["card"], padx=18, pady=12)
        top.pack(fill=tk.X)
        self.section_title(top, "Products").pack(side=tk.LEFT)
        tk.Label(top, textvariable=self.row_count_var, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9)).pack(side=tk.LEFT, padx=(10, 0), pady=(3, 0))

        search_box = tk.Frame(top, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_box.pack(side=tk.RIGHT)
        tk.Label(search_box, text="⌕", bg=COLORS["input"], fg=COLORS["muted"], font=sans(12)).pack(side=tk.LEFT, padx=(10, 0))
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            width=30,
            bg=COLORS["input"],
            fg=COLORS["strong"],
            insertbackground=COLORS["strong"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=sans(10),
        )
        self.search_entry.pack(side=tk.LEFT, ipady=6, padx=(6, 12))
        self.add_placeholder(self.search_entry, self.search_var, "Search by ID, name, or category")
        self.search_entry.bind("<FocusIn>", lambda e: search_box.configure(highlightbackground=COLORS["primary"]), add="+")
        self.search_entry.bind("<FocusOut>", lambda e: search_box.configure(highlightbackground=COLORS["line"]), add="+")

        self.chip_frame = tk.Frame(card, bg=COLORS["card"], padx=18)
        self.chip_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Frame(card, bg=COLORS["line"], height=1).pack(fill=tk.X)

        table_area = tk.Frame(card, bg=COLORS["card"])
        table_area.pack(fill=tk.BOTH, expand=True)
        table_area.rowconfigure(0, weight=1)
        table_area.columnconfigure(0, weight=1)

        columns = tuple(TABLE_COLUMNS)
        self.tree = ttk.Treeview(table_area, columns=columns, show="headings", selectmode="browse")
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.heading(column, text=heading, anchor=anchor, command=lambda key=sort_key: self.sort_by(key))
            self.tree.column(column, width=width, minwidth=40, anchor=anchor, stretch=False)

        scrollbar = ttk.Scrollbar(table_area, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = tk.Frame(card, bg=COLORS["card"], padx=18, pady=6)
        footer.pack(fill=tk.X)
        tk.Label(footer, text="Click a row to edit it  ·  Click a column heading to sort", bg=COLORS["card"], fg=COLORS["faint"], font=sans(9)).pack(side=tk.LEFT)
        legend = tk.Frame(footer, bg=COLORS["card"])
        legend.pack(side=tk.RIGHT)
        for text, color in (("In stock", "green"), ("Low stock", "amber"), ("Out of stock", "red")):
            tk.Label(legend, text="●", bg=COLORS["card"], fg=COLORS[color], font=sans(9)).pack(side=tk.LEFT, padx=(12, 3))
            tk.Label(legend, text=text, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9)).pack(side=tk.LEFT)

        self.empty_label = tk.Label(table_area, bg=COLORS["card"], fg=COLORS["muted"], font=sans(10), justify=tk.CENTER)

        self.tree.tag_configure("even", background=COLORS["card"])
        self.tree.tag_configure("odd", background=COLORS["row_alt"])
        self.tree.tag_configure("low", background=COLORS["row_low"], foreground=COLORS["amber"])
        self.tree.tag_configure("out", background=COLORS["row_out"], foreground=COLORS["red"])

        self.tree.bind("<<TreeviewSelect>>", self.load_selected_product)
        self.tree.bind("<Delete>", lambda event: self.delete_product())
        self.tree.bind("<Configure>", self.fit_columns)

    def render_chips(self):
        for widget in self.chip_frame.winfo_children():
            widget.destroy()

        counts = {}
        for product in self.products:
            counts[product["category"]] = counts.get(product["category"], 0) + 1
        categories = ["All"] + [c for c in CATEGORIES if c in counts] + sorted(c for c in counts if c not in CATEGORIES)
        if self.category_filter not in categories:
            self.category_filter = "All"

        for category in categories:
            count = len(self.products) if category == "All" else counts[category]
            active = category == self.category_filter
            chip = FlatButton(
                self.chip_frame,
                f"{category}  {count}",
                lambda value=category: self.set_category_filter(value),
                COLORS["primary"] if active else COLORS["card"],
                "#ffffff" if active else COLORS["text"],
                COLORS["primary_hover"] if active else COLORS["card_high"],
                font_size=9,
                padx=12,
                pady=5,
                border=COLORS["primary"] if active else COLORS["line"],
                hover_fg="#ffffff" if active else COLORS["strong"],
                weight="bold" if active else "normal",
            )
            chip.pack(side=tk.LEFT, padx=(0, 8))

    def add_placeholder(self, entry, variable, text):
        """Show grey hint text inside an empty entry box."""
        hint = tk.Label(entry, text=text, bg=COLORS["input"], fg=COLORS["faint"], font=sans(10), cursor="xterm")

        def update(*args):
            if variable.get() or entry.focus_get() == entry:
                hint.place_forget()
            else:
                hint.place(x=0, rely=0.5, anchor=tk.W)

        hint.bind("<Button-1>", lambda e: entry.focus_set())
        entry.bind("<FocusIn>", update, add="+")
        entry.bind("<FocusOut>", update, add="+")
        self.placeholder_trace = variable.trace_add("write", update)
        update()

    def fit_columns(self, event):
        """Stretch or shrink the columns so the table always fits without side scrolling."""
        base_total = sum(width for heading, width, anchor, sort_key in TABLE_COLUMNS.values())
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.column(column, width=int(width * event.width / base_total))

    def build_bottom_row(self, parent):
        row = tk.Frame(parent, bg=COLORS["page"], height=128)
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))
        row.pack_propagate(False)
        row.columnconfigure(0, weight=3, uniform="bottom")
        row.columnconfigure(1, weight=2, uniform="bottom")
        row.rowconfigure(0, weight=1)

        # Activity log
        outer, log_card = self.panel(row, padx=16, pady=10)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        top = tk.Frame(log_card, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text="Activity Log", bg=COLORS["card"], fg=COLORS["strong"], font=sans(10, "bold")).pack(side=tk.LEFT)
        tk.Label(top, text="This session", bg=COLORS["card"], fg=COLORS["faint"], font=sans(9)).pack(side=tk.RIGHT)

        self.log_box = tk.Text(
            log_card,
            height=4,
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=sans(9),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=6,
            wrap=tk.WORD,
            cursor="arrow",
            spacing1=2,
            spacing3=2,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)
        for name in set(LOG_COLORS.values()):
            self.log_box.tag_configure(name, foreground=COLORS[name], font=sans(9, "bold"))
        self.log_box.tag_configure("time", foreground=COLORS["faint"], font=(theme.MONO, 8))
        self.log_box.configure(state=tk.DISABLED)
        for entry in self.log_entries:
            self.write_log_line(*entry)

        # Product inspector
        outer, inspector = self.panel(row, padx=16, pady=10)
        outer.grid(row=0, column=1, sticky="nsew")
        top = tk.Frame(inspector, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text="Product Inspector", bg=COLORS["card"], fg=COLORS["strong"], font=sans(10, "bold")).pack(side=tk.LEFT)
        self.inspect_pill = tk.Label(top, bg=COLORS["card"], font=sans(9, "bold"), padx=8, pady=1)
        self.inspect_pill.pack(side=tk.RIGHT)

        heading = tk.Frame(inspector, bg=COLORS["card"])
        heading.pack(fill=tk.X, pady=(6, 0))
        names = tk.Frame(heading, bg=COLORS["card"])
        names.pack(side=tk.LEFT)
        self.ins_name = tk.Label(names, bg=COLORS["card"], fg=COLORS["strong"], font=sans(10, "bold"), anchor=tk.W)
        self.ins_name.pack(anchor=tk.W)
        self.ins_id = tk.Label(names, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), anchor=tk.W)
        self.ins_id.pack(anchor=tk.W)
        self.ins_price = tk.Label(heading, bg=COLORS["card"], fg=COLORS["primary"], font=sans(10, "bold"))
        self.ins_price.pack(side=tk.RIGHT, anchor=tk.N)

        self.stock_meter = tk.Canvas(inspector, height=16, bg=COLORS["card"], highlightthickness=0)
        self.stock_meter.pack(fill=tk.X, pady=(6, 2))
        self.stock_meter.bind("<Configure>", lambda event: self.update_inspector())

        self.ins_details = tk.Label(inspector, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), justify=tk.LEFT, anchor=tk.W)
        self.ins_details.pack(fill=tk.X)

    def build_form(self, parent):
        outer, form = self.panel(parent, padx=20, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(form, bg=COLORS["card"])
        header.pack(fill=tk.X)
        self.mode_badge = tk.Label(header, font=sans(8, "bold"), padx=8, pady=2)
        self.mode_badge.pack(side=tk.RIGHT, anchor=tk.N)
        titles = tk.Frame(header, bg=COLORS["card"])
        titles.pack(side=tk.LEFT)
        self.form_title = self.section_title(titles, "Add a Product")
        self.form_title.pack(anchor=tk.W)
        self.form_subtitle = tk.Label(titles, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), wraplength=250, justify=tk.LEFT)
        self.form_subtitle.pack(anchor=tk.W, pady=(2, 0))

        tk.Frame(form, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(10, 0))

        self.name_entry = self.create_input(form, "Product Name", self.product_name_var)
        self.create_category_input(form)

        numbers = tk.Frame(form, bg=COLORS["card"])
        numbers.pack(fill=tk.X)
        numbers.columnconfigure((0, 1), weight=1, uniform="numbers")
        quantity_box = tk.Frame(numbers, bg=COLORS["card"])
        quantity_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        price_box = tk.Frame(numbers, bg=COLORS["card"])
        price_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.quantity_entry = self.create_input(quantity_box, "Quantity (pcs)", self.quantity_var, width=10)
        self.price_entry = self.create_input(price_box, "Unit Price (PHP)", self.unit_price_var, width=10)

        total_box = tk.Frame(form, bg=COLORS["primary_soft"], padx=14, pady=8)
        total_box.pack(fill=tk.X, pady=(14, 0))
        tk.Label(total_box, text="Computed Total", bg=COLORS["primary_soft"], fg=COLORS["muted"], font=sans(9, "bold")).pack(side=tk.LEFT)
        tk.Label(total_box, textvariable=self.item_total_var, bg=COLORS["primary_soft"], fg=COLORS["primary"], font=sans(13, "bold")).pack(side=tk.RIGHT)

        self.error_label = tk.Label(
            form,
            textvariable=self.error_var,
            bg=COLORS["red_soft"],
            fg=COLORS["red"],
            font=sans(9, "bold"),
            wraplength=280,
            justify=tk.LEFT,
            anchor=tk.W,
            padx=10,
            pady=7,
        )
        self.error_var.trace_add("write", self.show_or_hide_error)

        buttons = tk.Frame(form, bg=COLORS["card"])
        buttons.pack(fill=tk.X, side=tk.BOTTOM)
        buttons.columnconfigure((0, 1), weight=1, uniform="buttons")

        self.add_button = FlatButton(
            buttons, "✓  Add Product", self.add_product, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"], border=COLORS["button"]
        )
        self.add_button.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 8))
        self.update_button = FlatButton(
            buttons, "⟳  Update", self.update_product, COLORS["card"], COLORS["strong"], COLORS["card_high"], border=COLORS["line_high"]
        )
        self.update_button.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 8))
        self.delete_button = FlatButton(
            buttons, "✕  Delete", self.delete_product, COLORS["red_soft"], COLORS["red"], COLORS["red_hover"], border=COLORS["red_line"]
        )
        self.delete_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        FlatButton(
            buttons, "Clear Fields", self.clear_fields, COLORS["card"], COLORS["muted"], COLORS["card_high"], border=COLORS["line"], hover_fg=COLORS["strong"]
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def show_or_hide_error(self, *args):
        if self.error_var.get():
            self.error_label.pack(fill=tk.X, pady=(10, 0))
        else:
            self.error_label.pack_forget()

    def create_input(self, parent, label, variable, width=30):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        tk.Label(wrapper, text=label, bg=COLORS["card"], fg=COLORS["text"], font=sans(9, "bold")).pack(anchor=tk.W)
        entry = tk.Entry(
            wrapper,
            textvariable=variable,
            width=width,
            bg=COLORS["input"],
            fg=COLORS["strong"],
            insertbackground=COLORS["strong"],
            selectbackground=COLORS["primary"],
            selectforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line_high"],
            highlightcolor=COLORS["primary"],
            font=sans(11),
        )
        entry.pack(fill=tk.X, pady=(4, 0), ipady=6, ipadx=8)
        entry.bind("<Return>", lambda event: self.save_from_keyboard())
        return entry

    def create_category_input(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        tk.Label(wrapper, text="Category", bg=COLORS["card"], fg=COLORS["text"], font=sans(9, "bold")).pack(anchor=tk.W)
        combo = ttk.Combobox(
            wrapper,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="normal",
            width=28,
            font=sans(11),
        )
        combo.pack(fill=tk.X, pady=(4, 0))
        self.category_entry = combo
        combo.bind("<Return>", lambda event: self.save_from_keyboard())

    def build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["page"])
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        tk.Label(footer, text="Product Inventory System  ·  IM102", bg=COLORS["page"], fg=COLORS["faint"], font=sans(9)).pack(side=tk.LEFT)
        shortcuts = tk.Frame(footer, bg=COLORS["page"])
        shortcuts.pack(side=tk.RIGHT)
        for key, action in (("Enter", "Save"), ("Esc", "Clear"), ("Del", "Delete"), ("Ctrl+F", "Search"), ("Ctrl+L", "Theme")):
            tk.Label(
                shortcuts, text=key, bg=COLORS["card"], fg=COLORS["text"], font=(theme.MONO, 8), padx=5,
                highlightthickness=1, highlightbackground=COLORS["line"],
            ).pack(side=tk.LEFT, padx=(14, 4))
            tk.Label(shortcuts, text=action, bg=COLORS["page"], fg=COLORS["muted"], font=sans(9)).pack(side=tk.LEFT)

    def bind_shortcuts(self):
        self.root.bind("<Escape>", lambda event: self.clear_fields())
        self.root.bind("<Control-f>", lambda event: self.search_entry.focus_set())
        self.root.bind("<Control-F>", lambda event: self.search_entry.focus_set())
        self.root.bind("<Control-l>", lambda event: self.toggle_theme())
        self.root.bind("<Control-L>", lambda event: self.toggle_theme())

    # ---------------------------------------------------------------- feedback

    def show_toast(self, message, kind="success"):
        accent = {"success": COLORS["green"], "info": COLORS["primary"], "error": COLORS["red"]}[kind]
        icon = {"success": "✓", "info": "ℹ", "error": "⚠"}[kind]
        self.toast_stripe.configure(bg=accent)
        self.toast_label.configure(text=f"{icon}   {message}")
        self.toast.place(relx=0.5, y=24, anchor=tk.N)
        self.toast.lift()

        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(3200, self.toast.place_forget)

    def log(self, kind, message):
        entry = (datetime.now().strftime("%H:%M:%S"), kind, message)
        self.log_entries.append(entry)
        self.log_entries = self.log_entries[-100:]
        self.write_log_line(*entry)

    def write_log_line(self, time_text, kind, message):
        self.log_box.configure(state=tk.NORMAL)
        if self.log_box.index("end-1c") != "1.0":
            self.log_box.insert(tk.END, "\n")
        self.log_box.insert(tk.END, f"{time_text} ", "time")
        self.log_box.insert(tk.END, f"[{kind}]", LOG_COLORS.get(kind, "muted"))
        self.log_box.insert(tk.END, f" {message}")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def show_error(self, message, widget=None):
        self.error_var.set(f"⚠  {message}")
        if widget is not None:
            widget.focus_set()

    def set_edit_mode(self, editing):
        self.update_button.set_enabled(editing)
        self.delete_button.set_enabled(editing)
        if editing:
            self.form_title.configure(text="Edit Product")
            self.form_subtitle.configure(text=f"Change the details of P{self.selected_product_id:03d}, then click Update.")
            self.mode_badge.configure(text="EDITING", bg=COLORS["amber_soft"], fg=COLORS["amber"])
        else:
            self.form_title.configure(text="Add a Product")
            self.form_subtitle.configure(text="Type the details, or click a row to edit.")
            self.mode_badge.configure(text="NEW", bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self.update_inspector()

    def update_inspector(self):
        if not hasattr(self, "stock_meter"):
            return

        product = self.find_product(self.selected_product_id)
        meter = self.stock_meter
        meter.delete("all")
        width = max(meter.winfo_width(), 100)

        if product is None:
            self.inspect_pill.configure(text="No product selected", fg=COLORS["faint"], bg=COLORS["card"])
            self.ins_name.configure(text="Click a product in the table")
            self.ins_id.configure(text="Its details and stock level will show here.")
            self.ins_price.configure(text="")
            self.ins_details.configure(text="")
            meter.create_rectangle(0, 5, width, 11, outline="", fill=COLORS["card_high"])
            return

        quantity = product["quantity"]
        if quantity == 0:
            status, key = "Out of stock", "red"
        elif quantity < database.LOW_STOCK_THRESHOLD:
            status, key = "Low stock", "amber"
        else:
            status, key = "In stock", "green"
        color = COLORS[key]

        self.inspect_pill.configure(text=f"●  {status}", fg=color, bg=COLORS[f"{key}_soft"])
        name = product["product_name"]
        self.ins_name.configure(text=name if len(name) <= 28 else name[:27] + "…")
        self.ins_id.configure(text=f"P{product['product_id']:03d}  ·  {product['category']}")
        self.ins_price.configure(text=f"{peso(product['unit_price'])} each")
        self.ins_details.configure(
            text=f"{quantity:,} pcs in stock  ·  Total value {peso(product['total'])}"
        )

        # Stock meter: the bar is this product's stock compared with the biggest stock in the list.
        biggest = max(max(p["quantity"] for p in self.products), database.LOW_STOCK_THRESHOLD * 2)
        meter.create_rectangle(0, 5, width, 11, outline="", fill=COLORS["card_high"])
        meter.create_rectangle(0, 5, max(int(width * quantity / biggest), 3), 11, outline="", fill=color)
        threshold_x = int(width * database.LOW_STOCK_THRESHOLD / biggest)
        meter.create_line(threshold_x, 1, threshold_x, 15, fill=COLORS["red"], dash=(2, 2))

    def start_new_product(self):
        self.clear_fields()
        self.name_entry.focus_set()

    def set_category_filter(self, category):
        self.category_filter = category
        self.render_table()

    def toggle_theme(self):
        """Switch between dark and light mode by rebuilding the screen with the new colors."""
        new_mode = "light" if theme.MODE == "dark" else "dark"
        theme.set_mode(new_mode)

        if self.toast_job:
            self.root.after_cancel(self.toast_job)
            self.toast_job = None
        if self.placeholder_trace:
            self.search_var.trace_remove("write", self.placeholder_trace)
            self.placeholder_trace = None
        viewer_was_open = self.viewer_is_open()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.viewer = None

        # The typed form values, search text, and log are kept because they live outside the widgets.
        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.refresh_data()
        self.set_edit_mode(self.selected_product_id is not None)
        self.log("THEME", f"Switched to {new_mode} mode.")
        if viewer_was_open:
            self.open_database_viewer()

    def viewer_is_open(self):
        return self.viewer is not None and self.viewer.root.winfo_exists()

    def open_database_viewer(self):
        """Open the DB Records window, or bring it to the front if it is already open."""
        import database_viewer

        if self.viewer_is_open():
            self.viewer.load_records()
            self.viewer.root.deiconify()
            self.viewer.root.lift()
            return

        window = tk.Toplevel(self.root)
        self.viewer = database_viewer.DatabaseViewer(window)

    # ------------------------------------------------------------------- CRUD

    def validate_inputs(self):
        product_name = self.product_name_var.get().strip()
        category = self.category_var.get().strip()
        quantity_text = self.quantity_var.get().strip()
        price_text = self.unit_price_var.get().strip()

        self.error_var.set("")

        if not product_name:
            self.show_error("Please enter a product name.", self.name_entry)
            return None

        if not category:
            self.show_error("Please enter a category.", self.category_entry)
            return None

        quantity = parse_quantity(quantity_text)
        if quantity is None:
            self.show_error("Quantity must be a whole number.", self.quantity_entry)
            return None

        if quantity < 0:
            self.show_error("Quantity cannot be negative.", self.quantity_entry)
            return None

        unit_price = parse_price(price_text)
        if unit_price is None or unit_price < 0:
            self.show_error("Please enter a valid price, like 25 or 8.50.", self.price_entry)
            return None

        return product_name, category, quantity, unit_price

    def save_from_keyboard(self):
        if self.selected_product_id is None:
            self.add_product()
        else:
            self.update_product()

    def add_product(self):
        values = self.validate_inputs()
        if values is None:
            return

        try:
            result = database.add_product(*values)
        except sqlite3.DatabaseError:
            self.log("ERROR", "Unable to save changes.")
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        name, category, quantity, unit_price = values
        if result == "restocked":
            self.log("RESTOCK", f"{name} already exists, so {quantity} pcs were added to its stock.")
            self.show_toast("Same product already exists, so its quantity was increased.", "info")
        else:
            self.log("ADD", f"Added {name} ({category}), {quantity} pcs @ {peso(unit_price)}.")
            self.show_toast("Product added successfully.")

    def update_product(self):
        if self.selected_product_id is None:
            self.show_error("Please select a product to update.")
            return

        values = self.validate_inputs()
        if values is None:
            return

        product_id = self.selected_product_id
        try:
            result = database.update_product(product_id, *values)
        except sqlite3.DatabaseError:
            self.log("ERROR", "Unable to save changes.")
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        if result == "duplicate":
            self.show_error("Another product already has the same name, category, and price.", self.name_entry)
            return

        self.refresh_data()
        self.clear_fields()
        self.log("UPDATE", f"P{product_id:03d} {values[0]} updated: {values[2]} pcs @ {peso(values[3])}.")
        self.show_toast("Product updated successfully.")

    def delete_product(self):
        if self.selected_product_id is None:
            self.show_error("Please select a product to delete.")
            return

        product_id = self.selected_product_id
        product = self.find_product(product_id)
        name = product["product_name"] if product else self.product_name_var.get()
        confirmed = messagebox.askyesno(
            "Delete Product",
            f"Are you sure you want to delete \"{name}\"?",
        )
        if not confirmed:
            return

        try:
            database.delete_product(product_id)
        except sqlite3.DatabaseError:
            self.log("ERROR", "Unable to save changes.")
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        self.log("DELETE", f"P{product_id:03d} {name} was deleted.")
        self.show_toast("Product deleted successfully.")

    def clear_fields(self):
        self.selected_product_id = None
        self.product_name_var.set("")
        self.category_var.set("School Supplies")
        self.quantity_var.set("")
        self.unit_price_var.set("")
        self.error_var.set("")
        self.update_item_total()
        if hasattr(self, "tree"):
            self.tree.selection_remove(self.tree.selection())
        if hasattr(self, "update_button"):
            self.set_edit_mode(False)

    def find_product(self, product_id):
        return next((p for p in self.products if p["product_id"] == product_id), None)

    def load_selected_product(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        product_id = int(selected_items[0])
        if product_id == self.selected_product_id:
            return
        product = self.find_product(product_id)
        if product is None:
            return

        self.selected_product_id = product_id
        self.product_name_var.set(product["product_name"])
        self.category_var.set(product["category"])
        self.quantity_var.set(str(product["quantity"]))
        self.unit_price_var.set(f"{product['unit_price']:.2f}")
        self.error_var.set("")
        self.update_item_total()
        self.set_edit_mode(True)

    def update_item_total(self, *args):
        quantity = parse_quantity(self.quantity_var.get() or "0")
        price = parse_price(self.unit_price_var.get() or "0")
        if quantity is None or price is None:
            self.item_total_var.set(peso(0))
            return

        self.item_total_var.set(peso(quantity * price))

    # ------------------------------------------------------------------ table

    def sort_by(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = False
        self.render_table()

    def update_sort_arrows(self):
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            arrow = ""
            if sort_key == self.sort_key and column != "status":
                arrow = " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(column, text=heading + arrow)

    def refresh_data(self):
        self.products = [
            dict(product, total=product["quantity"] * product["unit_price"]) for product in database.get_products()
        ]
        self.render_table()

        totals = database.get_dashboard_totals()
        self.total_value_var.set(peso(totals["total_value"]))
        self.total_products_var.set(f"{totals['total_products']:,}")
        self.total_units_var.set(f"{totals['total_stock_units']:,} units")

        low = [p for p in self.products if p["quantity"] < database.LOW_STOCK_THRESHOLD]
        out = [p for p in low if p["quantity"] == 0]
        self.low_stock_var.set(f"{len(low)}")
        self.low_stock_detail_var.set(short_list(low) if low else "All stock levels are OK")
        self.out_stock_var.set(f"{len(out)}")
        self.out_stock_detail_var.set(short_list(out) if out else "Nothing is out of stock")
        self.update_inspector()
        if self.viewer_is_open():
            self.viewer.load_records()

    def render_table(self):
        self.render_chips()

        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip().lower()
        products = [
            product
            for product in self.products
            if (self.category_filter == "All" or product["category"] == self.category_filter)
            and (
                search in product["product_name"].lower()
                or search in product["category"].lower()
                or search in f"p{product['product_id']:03d}"
            )
        ]

        def sort_value(product):
            value = product[self.sort_key]
            return value.lower() if isinstance(value, str) else value

        products.sort(key=sort_value, reverse=self.sort_reverse)

        for index, product in enumerate(products):
            product_id = product["product_id"]
            quantity = product["quantity"]

            if quantity == 0:
                status, status_tag = "✕  Out of stock", "out"
            elif quantity < database.LOW_STOCK_THRESHOLD:
                status, status_tag = "▲  Low stock", "low"
            else:
                status, status_tag = "✓  In stock", None

            tags = ["even" if index % 2 == 0 else "odd"]
            if status_tag:
                tags.append(status_tag)

            self.tree.insert(
                "",
                tk.END,
                iid=str(product_id),
                values=(
                    f"P{product_id:03d}",
                    product["product_name"],
                    product["category"],
                    f"{quantity:,} pcs",
                    status,
                    peso(product["unit_price"]),
                    peso(product["total"]),
                ),
                tags=tuple(tags),
            )

        if self.selected_product_id is not None and self.tree.exists(str(self.selected_product_id)):
            self.tree.selection_set(str(self.selected_product_id))

        self.update_sort_arrows()
        self.row_count_var.set(f"Showing {len(products)} of {len(self.products)} products")

        if products:
            self.empty_label.place_forget()
        else:
            if self.products:
                self.empty_label.configure(text="No products match your search or filter.\nTry another word or click All.")
            else:
                self.empty_label.configure(text="No products yet.\nAdd your first product using the form on the right.")
            self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)


def main():
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
