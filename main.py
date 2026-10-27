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
    "product_id": ("ID", 60, tk.W, "product_id"),
    "product_name": ("PRODUCT", 190, tk.W, "product_name"),
    "category": ("CATEGORY", 130, tk.W, "category"),
    "quantity": ("STOCK", 70, tk.E, "quantity"),
    "status": ("STATUS", 105, tk.W, "quantity"),
    "unit_price": ("UNIT PRICE", 110, tk.E, "unit_price"),
    "total": ("TOTAL AMOUNT", 130, tk.E, "total"),
}

LOG_COLORS = {"BOOT": "primary", "ADD": "green", "RESTOCK": "green", "UPDATE": "primary", "DELETE": "red", "ALERT": "amber", "ERROR": "red", "THEME": "muted"}


def mono(size, weight="normal"):
    return (theme.MONO, size, weight)


def peso(amount):
    return f"PHP {amount:,.2f}"


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Product Inventory System")
        self.root.geometry("1320x760")
        self.root.minsize(1180, 700)

        self.selected_product_id = None
        self.products = []
        self.category_filter = "All"
        self.sort_key = "product_id"
        self.sort_reverse = True
        self.toast_job = None
        self.placeholder_trace = None
        self.log_entries = []

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
        self.total_products_var = tk.StringVar(value="0 PRODUCTS")
        self.total_units_var = tk.StringVar(value="(0 UNITS)")
        self.low_stock_var = tk.StringVar(value="0 ALERTS")
        self.low_stock_detail_var = tk.StringVar(value="ALL STOCK LEVELS OK")

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
        shell = tk.Frame(self.root, bg=COLORS["page"], padx=22, pady=16)
        shell.pack(fill=tk.BOTH, expand=True)

        self.build_header(shell)
        self.build_kpis(shell)
        self.build_footer(shell)

        main = tk.Frame(shell, bg=COLORS["page"])
        main.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=COLORS["page"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(main, bg=COLORS["page"], width=360)
        right.grid(row=0, column=1, sticky="ns")

        self.build_filter_bar(left)
        self.build_bottom_row(left)
        self.build_table(left)
        self.build_form(right)

        self.toast = tk.Label(self.root, bg=COLORS["card"], fg=COLORS["text"], font=mono(9, "bold"), padx=16, pady=10)

    def panel(self, parent, accent=None, side="top"):
        """A bordered panel with an optional 2px accent stripe on the top or left."""
        outer = tk.Frame(parent, bg=COLORS["line"])
        if accent:
            stripe = tk.Frame(outer, bg=accent, height=2, width=2)
            stripe.pack(side=tk.TOP if side == "top" else tk.LEFT, fill=tk.X if side == "top" else tk.Y)
        inner = tk.Frame(outer, bg=COLORS["card"])
        if side == "top" and accent:
            inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))
        elif accent:
            inner.pack(fill=tk.BOTH, expand=True, padx=(0, 1), pady=1)
        else:
            inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["page"])
        header.pack(fill=tk.X)

        logo = tk.Canvas(header, width=40, height=40, bg=COLORS["page"], highlightthickness=0)
        logo.pack(side=tk.LEFT)
        logo.create_oval(2, 2, 38, 38, outline=COLORS["strong"], width=1)
        star = (20, 7, 23, 16, 32, 16, 25, 22, 28, 31, 20, 25, 12, 31, 15, 22, 8, 16, 17, 16)
        logo.create_polygon(star, fill=COLORS["primary"], outline="")

        names = tk.Frame(header, bg=COLORS["page"])
        names.pack(side=tk.LEFT, padx=(12, 0))
        title = tk.Frame(names, bg=COLORS["page"])
        title.pack(anchor=tk.W)
        tk.Label(title, text="PRODUCT INVENTORY", bg=COLORS["page"], fg=COLORS["strong"], font=mono(16, "bold")).pack(side=tk.LEFT)
        tk.Label(title, text=" // IM102", bg=COLORS["page"], fg=COLORS["primary"], font=mono(11, "bold")).pack(side=tk.LEFT, pady=(4, 0))
        tk.Label(
            title,
            text="SQLITE",
            bg=COLORS["primary_soft"],
            fg=COLORS["primary"],
            font=mono(7, "bold"),
            padx=6,
            pady=1,
            highlightthickness=1,
            highlightbackground=COLORS["primary_line"],
        ).pack(side=tk.LEFT, padx=(10, 0), pady=(3, 0))

        subtitle = tk.Frame(names, bg=COLORS["page"])
        subtitle.pack(anchor=tk.W, pady=(3, 0))
        tk.Label(subtitle, text="REAL-TIME STOCK TRACKING & CRUD OPERATIONS", bg=COLORS["page"], fg=COLORS["muted"], font=mono(8)).pack(side=tk.LEFT)
        tk.Label(subtitle, text="  |  ", bg=COLORS["page"], fg=COLORS["line_high"], font=mono(8)).pack(side=tk.LEFT)
        tk.Label(subtitle, text="● DATABASE: LIVE", bg=COLORS["page"], fg=COLORS["green"], font=mono(8)).pack(side=tk.LEFT)

        right = tk.Frame(header, bg=COLORS["page"])
        right.pack(side=tk.RIGHT)

        self.count_badge = tk.Label(
            right,
            text="00",
            bg=COLORS["card"],
            fg=COLORS["primary"],
            font=mono(11, "bold"),
            width=3,
            pady=6,
            highlightthickness=1,
            highlightbackground=COLORS["line_high"],
        )
        self.count_badge.pack(side=tk.RIGHT)

        FlatButton(
            right,
            "+  NEW PRODUCT",
            self.start_new_product,
            COLORS["primary_soft"],
            COLORS["strong"],
            COLORS["primary_line"],
            border=COLORS["primary"],
        ).pack(side=tk.RIGHT, padx=(0, 10))

        FlatButton(
            right,
            "▤  DB RECORDS",
            self.open_database_viewer,
            COLORS["card"],
            COLORS["muted"],
            COLORS["card_high"],
            border=COLORS["line"],
            hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 10))

        toggle_text = "☀  LIGHT MODE" if theme.MODE == "dark" else "☾  DARK MODE"
        FlatButton(
            right,
            toggle_text,
            self.toggle_theme,
            COLORS["card"],
            COLORS["muted"],
            COLORS["card_high"],
            border=COLORS["line"],
            hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 10))

        tk.Frame(parent, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(12, 0))

    def build_kpis(self, parent):
        strip = tk.Frame(parent, bg=COLORS["page"])
        strip.pack(fill=tk.X, pady=(12, 0))
        for column in range(4):
            strip.columnconfigure(column, weight=1, uniform="kpi")

        cards = [
            ("TOTAL INVENTORY VALUE", "₱", COLORS["primary"], (self.total_value_var,), "QUANTITY × UNIT PRICE, ALL PRODUCTS", COLORS["muted"]),
            ("REGISTERED PRODUCTS", "▦", COLORS["green"], (self.total_products_var, self.total_units_var), "100% SAVED TO DISK", COLORS["green"]),
            ("LOW STOCK ALERT", "▲", COLORS["red"], (self.low_stock_var,), self.low_stock_detail_var, COLORS["red"]),
            ("DATABASE", "⛁", COLORS["muted"], ("INVENTORY.DB",), f"SQLITE // LOW STOCK BELOW {database.LOW_STOCK_THRESHOLD} PCS", COLORS["muted"]),
        ]

        for index, (title, icon, accent, values, note, note_color) in enumerate(cards):
            outer, card = self.panel(strip, accent, side="left")
            outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            card.configure(padx=12, pady=9)

            top = tk.Frame(card, bg=COLORS["card"])
            top.pack(fill=tk.X)
            tk.Label(top, text=title, bg=COLORS["card"], fg=COLORS["muted"], font=mono(8)).pack(side=tk.LEFT)
            tk.Label(top, text=icon, bg=COLORS["card"], fg=accent, font=mono(10, "bold")).pack(side=tk.RIGHT)

            value_row = tk.Frame(card, bg=COLORS["card"])
            value_row.pack(fill=tk.X, pady=(3, 0))
            value_color = COLORS["red"] if accent == COLORS["red"] else COLORS["strong"]
            for position, value in enumerate(values):
                options = {"textvariable": value} if isinstance(value, tk.StringVar) else {"text": value}
                if position == 0:
                    tk.Label(value_row, bg=COLORS["card"], fg=value_color, font=mono(13, "bold"), **options).pack(side=tk.LEFT)
                else:
                    tk.Label(value_row, bg=COLORS["card"], fg=COLORS["muted"], font=mono(9), **options).pack(side=tk.LEFT, padx=(8, 0), pady=(3, 0))

            note_options = {"textvariable": note} if isinstance(note, tk.StringVar) else {"text": note}
            tk.Label(card, bg=COLORS["card"], fg=note_color, font=mono(7), anchor=tk.W, **note_options).pack(fill=tk.X, pady=(2, 0))

    def build_filter_bar(self, parent):
        bar = tk.Frame(parent, bg=COLORS["page"])
        bar.pack(fill=tk.X)

        self.chip_frame = tk.Frame(bar, bg=COLORS["page"])
        self.chip_frame.pack(side=tk.LEFT)

        search_box = tk.Frame(bar, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_box.pack(side=tk.RIGHT)
        tk.Label(search_box, text="⌕", bg=COLORS["input"], fg=COLORS["primary"], font=mono(11)).pack(side=tk.RIGHT, padx=(2, 8))
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            width=26,
            bg=COLORS["input"],
            fg=COLORS["strong"],
            insertbackground=COLORS["strong"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=mono(9),
        )
        self.search_entry.pack(side=tk.LEFT, ipady=6, padx=(10, 2))
        self.add_placeholder(self.search_entry, self.search_var, "SEARCH ID, NAME, CATEGORY...")
        self.search_entry.bind("<FocusIn>", lambda e: search_box.configure(highlightbackground=COLORS["primary"]), add="+")
        self.search_entry.bind("<FocusOut>", lambda e: search_box.configure(highlightbackground=COLORS["line"]), add="+")

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
                f"{category.upper()} [{count}]",
                lambda value=category: self.set_category_filter(value),
                COLORS["primary_soft"] if active else COLORS["card"],
                COLORS["strong"] if active else COLORS["muted"],
                COLORS["primary_soft"] if active else COLORS["card_high"],
                font_size=8,
                padx=9,
                pady=4,
                border=COLORS["primary"] if active else COLORS["line"],
                hover_fg=COLORS["strong"],
            )
            chip.pack(side=tk.LEFT, padx=(0, 6))

    def add_placeholder(self, entry, variable, text):
        """Show grey hint text inside an empty entry box."""
        hint = tk.Label(entry, text=text, bg=COLORS["input"], fg=COLORS["faint"], font=mono(9), cursor="xterm")

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

    def build_table(self, parent):
        outer, table_card = self.panel(parent)
        outer.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        table_card.rowconfigure(0, weight=1)
        table_card.columnconfigure(0, weight=1)

        columns = tuple(TABLE_COLUMNS)
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.heading(column, text=heading, anchor=anchor, command=lambda key=sort_key: self.sort_by(key))
            self.tree.column(column, width=width, minwidth=40, anchor=anchor, stretch=False)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = tk.Frame(table_card, bg=COLORS["card_high"], padx=10, pady=5)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Label(footer, textvariable=self.row_count_var, bg=COLORS["card_high"], fg=COLORS["muted"], font=mono(7)).pack(side=tk.LEFT)
        tk.Label(footer, text="  |  CLICK A ROW TO EDIT · CLICK A HEADING TO SORT", bg=COLORS["card_high"], fg=COLORS["faint"], font=mono(7)).pack(side=tk.LEFT)
        tk.Label(footer, text="● AUTO-CALCULATIONS ON", bg=COLORS["card_high"], fg=COLORS["green"], font=mono(7)).pack(side=tk.RIGHT)

        self.empty_label = tk.Label(table_card, bg=COLORS["card"], fg=COLORS["muted"], font=mono(9), justify=tk.CENTER)

        self.tree.tag_configure("even", background=COLORS["card"])
        self.tree.tag_configure("odd", background=COLORS["row_alt"])
        self.tree.tag_configure("low", foreground=COLORS["amber"])
        self.tree.tag_configure("out", foreground=COLORS["red"], background=COLORS["row_low"])

        self.tree.bind("<<TreeviewSelect>>", self.load_selected_product)
        self.tree.bind("<Delete>", lambda event: self.delete_product())
        self.tree.bind("<Configure>", self.fit_columns)

    def fit_columns(self, event):
        """Stretch or shrink the columns so the table always fits without side scrolling."""
        base_total = sum(width for heading, width, anchor, sort_key in TABLE_COLUMNS.values())
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.column(column, width=int(width * event.width / base_total))

    def build_bottom_row(self, parent):
        row = tk.Frame(parent, bg=COLORS["page"])
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        row.columnconfigure(0, weight=3, uniform="bottom")
        row.columnconfigure(1, weight=2, uniform="bottom")

        # Activity log
        outer, log_card = self.panel(row)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        log_card.configure(padx=10, pady=8)
        top = tk.Frame(log_card, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text="[ACTIVITY LOG]", bg=COLORS["card"], fg=COLORS["primary"], font=mono(8, "bold")).pack(side=tk.LEFT)
        tk.Label(top, text="THIS SESSION", bg=COLORS["card"], fg=COLORS["faint"], font=mono(7)).pack(side=tk.RIGHT)

        self.log_box = tk.Text(
            log_card,
            height=6,
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=mono(8),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=8,
            pady=6,
            wrap=tk.WORD,
            cursor="arrow",
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        for name in set(LOG_COLORS.values()):
            self.log_box.tag_configure(name, foreground=COLORS[name])
        self.log_box.tag_configure("time", foreground=COLORS["faint"])
        self.log_box.configure(state=tk.DISABLED)
        for entry in self.log_entries:
            self.write_log_line(*entry)

        # Inspector
        outer, inspector = self.panel(row)
        outer.grid(row=0, column=1, sticky="nsew")
        inspector.configure(padx=10, pady=8)
        top = tk.Frame(inspector, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text="[PRODUCT INSPECTOR]", bg=COLORS["card"], fg=COLORS["muted"], font=mono(8, "bold")).pack(side=tk.LEFT)
        self.inspect_pill = tk.Label(top, bg=COLORS["card"], font=mono(7, "bold"))
        self.inspect_pill.pack(side=tk.RIGHT)

        box = tk.Frame(inspector, bg=COLORS["page"], highlightthickness=1, highlightbackground=COLORS["line"], padx=10, pady=8)
        box.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        heading = tk.Frame(box, bg=COLORS["page"])
        heading.pack(fill=tk.X)
        names = tk.Frame(heading, bg=COLORS["page"])
        names.pack(side=tk.LEFT)
        self.ins_name = tk.Label(names, bg=COLORS["page"], fg=COLORS["strong"], font=mono(9, "bold"), anchor=tk.W)
        self.ins_name.pack(anchor=tk.W)
        self.ins_id = tk.Label(names, bg=COLORS["page"], fg=COLORS["muted"], font=mono(7), anchor=tk.W)
        self.ins_id.pack(anchor=tk.W)
        self.ins_price = tk.Label(heading, bg=COLORS["page"], fg=COLORS["primary"], font=mono(9, "bold"))
        self.ins_price.pack(side=tk.RIGHT, anchor=tk.N)

        self.stock_meter = tk.Canvas(box, height=22, bg=COLORS["page"], highlightthickness=0)
        self.stock_meter.pack(fill=tk.X, pady=(6, 4))
        self.stock_meter.bind("<Configure>", lambda event: self.update_inspector())

        self.ins_details = tk.Label(box, bg=COLORS["page"], fg=COLORS["muted"], font=mono(7), justify=tk.LEFT, anchor=tk.W)
        self.ins_details.pack(fill=tk.X)

    def build_form(self, parent):
        outer, form = self.panel(parent, COLORS["primary"])
        outer.pack(fill=tk.BOTH, expand=True)
        form.configure(padx=16, pady=14)

        header = tk.Frame(form, bg=COLORS["card"])
        header.pack(fill=tk.X)
        titles = tk.Frame(header, bg=COLORS["card"])
        titles.pack(side=tk.LEFT)
        tk.Label(titles, text="●  PRODUCT CONTROL PANEL", bg=COLORS["card"], fg=COLORS["strong"], font=mono(10, "bold")).pack(anchor=tk.W)
        self.form_subtitle = tk.Label(titles, bg=COLORS["card"], fg=COLORS["muted"], font=mono(7))
        self.form_subtitle.pack(anchor=tk.W, pady=(2, 0))
        self.mode_badge = tk.Label(header, font=mono(7, "bold"), padx=7, pady=2, highlightthickness=1)
        self.mode_badge.pack(side=tk.RIGHT, anchor=tk.N)

        self.name_entry = self.create_input(form, "PRODUCT NAME", self.product_name_var)
        self.create_category_input(form)

        numbers = tk.Frame(form, bg=COLORS["card"])
        numbers.pack(fill=tk.X)
        numbers.columnconfigure((0, 1), weight=1, uniform="numbers")
        quantity_box = tk.Frame(numbers, bg=COLORS["card"])
        quantity_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        price_box = tk.Frame(numbers, bg=COLORS["card"])
        price_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.quantity_entry = self.create_input(quantity_box, "QUANTITY (PCS)", self.quantity_var, width=10)
        self.price_entry = self.create_input(price_box, "UNIT PRICE (PHP)", self.unit_price_var, width=10)

        total_box = tk.Frame(form, bg=COLORS["primary_soft"], padx=12, pady=9, highlightthickness=1, highlightbackground=COLORS["primary_line"])
        total_box.pack(fill=tk.X, pady=(14, 0))
        tk.Label(total_box, text="COMPUTED TOTAL:", bg=COLORS["primary_soft"], fg=COLORS["muted"], font=mono(8)).pack(side=tk.LEFT)
        tk.Label(total_box, textvariable=self.item_total_var, bg=COLORS["primary_soft"], fg=COLORS["primary"], font=mono(11, "bold")).pack(side=tk.RIGHT)

        tk.Label(
            form,
            textvariable=self.error_var,
            bg=COLORS["card"],
            fg=COLORS["red"],
            font=mono(8, "bold"),
            wraplength=310,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 4))

        buttons = tk.Frame(form, bg=COLORS["card"])
        buttons.pack(fill=tk.X, side=tk.BOTTOM)
        buttons.columnconfigure((0, 1), weight=1, uniform="buttons")

        self.add_button = FlatButton(
            buttons, "✓  ADD PRODUCT", self.add_product, COLORS["button"], COLORS["button_text"], COLORS["primary"], pady=10, hover_fg="#ffffff"
        )
        self.add_button.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 8))
        self.update_button = FlatButton(
            buttons, "⟳  UPDATE", self.update_product, COLORS["card_high"], COLORS["text"], COLORS["line"], pady=10, border=COLORS["line_high"], hover_fg=COLORS["strong"]
        )
        self.update_button.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 8))
        self.delete_button = FlatButton(
            buttons, "✕  DELETE", self.delete_product, COLORS["red_soft"], COLORS["red"], COLORS["red_hover"], font_size=8, border=COLORS["red_line"]
        )
        self.delete_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        FlatButton(
            buttons, "⌫  CLEAR FIELDS", self.clear_fields, COLORS["card"], COLORS["muted"], COLORS["card_high"], font_size=8, border=COLORS["line"], hover_fg=COLORS["strong"]
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def create_input(self, parent, label, variable, width=30):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(12, 0))

        tk.Label(wrapper, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=mono(8)).pack(anchor=tk.W)
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
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["primary"],
            font=mono(10),
        )
        entry.pack(fill=tk.X, pady=(4, 0), ipady=6, ipadx=8)
        entry.bind("<Return>", lambda event: self.save_from_keyboard())
        return entry

    def create_category_input(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(12, 0))

        tk.Label(wrapper, text="CATEGORY", bg=COLORS["card"], fg=COLORS["muted"], font=mono(8)).pack(anchor=tk.W)
        combo = ttk.Combobox(
            wrapper,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="normal",
            width=28,
            font=mono(10),
        )
        combo.pack(fill=tk.X, pady=(4, 0), ipady=1)
        combo.bind("<Return>", lambda event: self.save_from_keyboard())

    def build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["page"])
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        tk.Frame(footer, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(0, 8))
        tk.Label(footer, text="PRODUCT INVENTORY SYSTEM // IM102", bg=COLORS["page"], fg=COLORS["faint"], font=mono(7)).pack(side=tk.LEFT)
        tk.Label(
            footer,
            text="ENTER SAVE  ·  ESC CLEAR  ·  DEL DELETE  ·  CTRL+F SEARCH  ·  CTRL+L THEME",
            bg=COLORS["page"],
            fg=COLORS["faint"],
            font=mono(7),
        ).pack(side=tk.RIGHT)

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
        self.toast.configure(text=f"{icon}  {message.upper()}", fg=accent, highlightthickness=1, highlightbackground=accent)
        self.toast.place(relx=1.0, rely=1.0, x=-22, y=-34, anchor=tk.SE)
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
        self.error_var.set(f"⚠  {message.upper()}")
        if widget is not None:
            widget.focus_set()

    def set_edit_mode(self, editing):
        self.update_button.set_enabled(editing)
        self.delete_button.set_enabled(editing)
        if editing:
            self.form_subtitle.configure(text=f"EDITING P{self.selected_product_id:03d}. CHANGE DETAILS, THEN UPDATE")
            self.mode_badge.configure(text="EDITING", bg=COLORS["amber_soft"], fg=COLORS["amber"], highlightbackground=COLORS["amber"])
        else:
            self.form_subtitle.configure(text="ADD A NEW PRODUCT OR SELECT A TABLE ROW")
            self.mode_badge.configure(text="READY", bg=COLORS["primary_soft"], fg=COLORS["primary"], highlightbackground=COLORS["primary_line"])
        self.update_inspector()

    def update_inspector(self):
        if not hasattr(self, "stock_meter"):
            return

        product = self.find_product(self.selected_product_id)
        meter = self.stock_meter
        meter.delete("all")
        width = max(meter.winfo_width(), 100)

        if product is None:
            self.inspect_pill.configure(text="IDLE // READY", fg=COLORS["faint"])
            self.ins_name.configure(text="SELECT ANY ITEM FROM THE TABLE")
            self.ins_id.configure(text="ID: --")
            self.ins_price.configure(text="--")
            self.ins_details.configure(text="CATEGORY: --\nQUANTITY: --     TOTAL VALUE: --")
            meter.create_line(0, 11, width, 11, fill=COLORS["line_high"], dash=(2, 3))
            return

        quantity = product["quantity"]
        if quantity == 0:
            status, color = "OUT OF STOCK", COLORS["red"]
        elif quantity < database.LOW_STOCK_THRESHOLD:
            status, color = "LOW STOCK", COLORS["amber"]
        else:
            status, color = "IN STOCK", COLORS["green"]

        self.inspect_pill.configure(text=f"● {status}", fg=color)
        self.ins_name.configure(text=product["product_name"].upper()[:30])
        self.ins_id.configure(text=f"ID: P{product['product_id']:03d}")
        self.ins_price.configure(text=peso(product["unit_price"]))
        self.ins_details.configure(
            text=f"CATEGORY: {product['category'].upper()}\nQUANTITY: {quantity:,} PCS     TOTAL VALUE: {peso(product['total'])}"
        )

        # Stock meter: the bar is this product's stock compared with the biggest stock in the list.
        biggest = max(max(p["quantity"] for p in self.products), database.LOW_STOCK_THRESHOLD * 2)
        meter.create_rectangle(0, 6, width, 16, outline=COLORS["line"], fill=COLORS["card"])
        meter.create_rectangle(0, 6, max(int(width * quantity / biggest), 2), 16, outline="", fill=color)
        threshold_x = int(width * database.LOW_STOCK_THRESHOLD / biggest)
        meter.create_line(threshold_x, 2, threshold_x, 20, fill=COLORS["red"], dash=(2, 2))

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
        for widget in self.root.winfo_children():
            widget.destroy()

        # The typed form values, search text, and log are kept because they live outside the widgets.
        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.refresh_data()
        self.set_edit_mode(self.selected_product_id is not None)
        self.log("THEME", f"Switched to {new_mode} mode.")

    def open_database_viewer(self):
        import database_viewer

        window = tk.Toplevel(self.root)
        database_viewer.DatabaseViewer(window)

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
            self.show_error("Please enter a category.")
            return None

        try:
            quantity = int(quantity_text)
        except ValueError:
            self.show_error("Quantity must be a whole number.", self.quantity_entry)
            return None

        if quantity < 0:
            self.show_error("Quantity cannot be negative.", self.quantity_entry)
            return None

        try:
            unit_price = float(price_text)
        except ValueError:
            self.show_error("Please enter a valid price.", self.price_entry)
            return None

        if unit_price < 0:
            self.show_error("Please enter a valid price.", self.price_entry)
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
            database.update_product(product_id, *values)
        except sqlite3.DatabaseError:
            self.log("ERROR", "Unable to save changes.")
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
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
        name = self.product_name_var.get()
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
        try:
            quantity = int(self.quantity_var.get() or 0)
            price = float(self.unit_price_var.get() or 0)
        except ValueError:
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
        self.total_products_var.set(f"{totals['total_products']:,} PRODUCTS")
        self.total_units_var.set(f"({totals['total_stock_units']:,} UNITS)")
        self.count_badge.configure(text=f"{totals['total_products']:02d}")

        low = [p for p in self.products if p["quantity"] < database.LOW_STOCK_THRESHOLD]
        self.low_stock_var.set(f"{len(low)} ALERT" + ("" if len(low) == 1 else "S"))
        if low:
            names = ", ".join(f"P{p['product_id']:03d} {p['product_name'].upper()}" for p in low[:3])
            self.low_stock_detail_var.set(names + (" ..." if len(low) > 3 else ""))
        else:
            self.low_stock_detail_var.set("ALL STOCK LEVELS OK")
        self.update_inspector()

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
                status, status_tag = "✕ OUT", "out"
            elif quantity < database.LOW_STOCK_THRESHOLD:
                status, status_tag = "▲ LOW STOCK", "low"
            else:
                status, status_tag = "● OK", None

            tags = ["even" if index % 2 == 0 else "odd"]
            if status_tag:
                tags.append(status_tag)

            self.tree.insert(
                "",
                tk.END,
                iid=str(product_id),
                values=(
                    f"P{product_id:03d}",
                    product["product_name"].upper(),
                    product["category"].upper(),
                    f"{quantity:,} PCS",
                    status,
                    peso(product["unit_price"]),
                    peso(product["total"]),
                ),
                tags=tuple(tags),
            )

        if self.selected_product_id is not None and self.tree.exists(str(self.selected_product_id)):
            self.tree.selection_set(str(self.selected_product_id))

        self.update_sort_arrows()
        self.row_count_var.set(f"SHOWING {len(products)} OF {len(self.products)} PRODUCTS")

        if products:
            self.empty_label.place_forget()
        else:
            if self.products:
                self.empty_label.configure(text="[NO PRODUCTS MATCH YOUR SEARCH OR FILTER]")
            else:
                self.empty_label.configure(text="[NO PRODUCTS YET]\nADD YOUR FIRST PRODUCT USING THE CONTROL PANEL")
            self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)


def main():
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
