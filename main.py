import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

import database
import theme
from theme import COLORS, FlatButton


CATEGORIES = ("School Supplies", "Food", "Drinks", "Cleaning", "Electronics", "Other")

# Table column -> (heading, width, anchor, key used for sorting)
TABLE_COLUMNS = {
    "product_id": ("ID", 56, tk.CENTER, "product_id"),
    "product_name": ("PRODUCT NAME", 170, tk.W, "product_name"),
    "category": ("CATEGORY", 120, tk.W, "category"),
    "quantity": ("QTY", 56, tk.CENTER, "quantity"),
    "unit_price": ("PRICE", 96, tk.E, "unit_price"),
    "total": ("AMOUNT", 106, tk.E, "total"),
    "status": ("STATUS", 84, tk.CENTER, "quantity"),
}


def font(size, weight="normal"):
    return (theme.FONT, size, weight)


def mono(size, weight="bold"):
    return (theme.MONO, size, weight)


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Product Inventory System")
        self.root.geometry("1280x740")
        self.root.minsize(1100, 660)

        self.selected_product_id = None
        self.products = []
        self.sort_key = "product_id"
        self.sort_reverse = True
        self.toast_job = None

        database.initialize_database()

        self.product_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value="School Supplies")
        self.quantity_var = tk.StringVar()
        self.unit_price_var = tk.StringVar()
        self.item_total_var = tk.StringVar(value="Php 0.00")
        self.search_var = tk.StringVar()
        self.form_title_var = tk.StringVar(value="New Product")
        self.form_note_var = tk.StringVar(value="Fill this out to save a product.")
        self.error_var = tk.StringVar()
        self.list_count_var = tk.StringVar()

        self.total_products_var = tk.StringVar(value="0")
        self.total_stock_units_var = tk.StringVar(value="0")
        self.low_stock_products_var = tk.StringVar(value="0")
        self.total_value_var = tk.StringVar(value="Php 0.00")

        theme.load_fonts(self.root)
        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.bind_shortcuts()
        self.refresh_data()
        self.set_edit_mode(False)

        self.quantity_var.trace_add("write", self.update_item_total)
        self.unit_price_var.trace_add("write", self.update_item_total)
        self.search_var.trace_add("write", lambda *args: self.render_table())

    # ------------------------------------------------------------------ layout

    def build_interface(self):
        shell = tk.Frame(self.root, bg=COLORS["page"])
        shell.pack(fill=tk.BOTH, expand=True)

        self.build_sidebar(shell)

        page = tk.Frame(shell, bg=COLORS["page"])
        page.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=26, pady=18)

        self.build_heading(page)
        self.build_dashboard(page)

        content = tk.Frame(page, bg=COLORS["page"])
        content.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self.build_form(content)
        self.build_table(content)

        self.toast = tk.Label(self.root, bg=COLORS["card_high"], fg=COLORS["text"], font=font(10, "bold"), padx=18, pady=12)

    def build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS["sidebar"], width=230)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Thin accent line on the right edge of the sidebar.
        tk.Frame(parent, bg=COLORS["line"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
        brand.pack(fill=tk.X, padx=20, pady=(24, 30))

        logo = tk.Canvas(brand, width=38, height=38, bg=COLORS["sidebar"], highlightthickness=0)
        logo.pack(side=tk.LEFT)
        self.draw_gradient_square(logo, 38, COLORS["primary"], COLORS["cyan"])
        logo.create_text(19, 19, text="PI", fill="#ffffff", font=font(12, "bold"))

        names = tk.Frame(brand, bg=COLORS["sidebar"])
        names.pack(side=tk.LEFT, padx=(12, 0))
        tk.Label(names, text="Inventory", bg=COLORS["sidebar"], fg=COLORS["text"], font=font(13, "bold")).pack(anchor=tk.W)
        tk.Label(names, text="IM102 Project", bg=COLORS["sidebar"], fg=COLORS["muted"], font=font(9)).pack(anchor=tk.W)

        tk.Label(sidebar, text="MENU", bg=COLORS["sidebar"], fg=COLORS["faint"], font=font(8, "bold")).pack(anchor=tk.W, padx=22, pady=(0, 8))

        active = tk.Frame(sidebar, bg=COLORS["primary_soft"])
        active.pack(fill=tk.X, padx=12)
        tk.Frame(active, bg=COLORS["primary"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(active, text="  Products", bg=COLORS["primary_soft"], fg="#ffffff", font=font(10, "bold"), pady=10, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X)

        viewer_link = FlatButton(
            sidebar,
            "  Database Records",
            self.open_database_viewer,
            COLORS["sidebar"],
            COLORS["muted"],
            COLORS["card_high"],
            pady=10,
        )
        viewer_link.configure(anchor=tk.W, font=font(10))
        viewer_link.pack(fill=tk.X, padx=12, pady=(4, 0))

        footer = tk.Frame(sidebar, bg=COLORS["sidebar"])
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

        tk.Label(footer, text="SHORTCUTS", bg=COLORS["sidebar"], fg=COLORS["faint"], font=font(8, "bold")).pack(anchor=tk.W, pady=(0, 6))
        for keys, action in (("Enter", "Save product"), ("Esc", "Clear form"), ("Del", "Delete selected"), ("Ctrl+F", "Search")):
            row = tk.Frame(footer, bg=COLORS["sidebar"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=keys, bg=COLORS["card_high"], fg=COLORS["text"], font=mono(8), padx=6, pady=1).pack(side=tk.LEFT)
            tk.Label(row, text=action, bg=COLORS["sidebar"], fg=COLORS["muted"], font=font(9)).pack(side=tk.LEFT, padx=(8, 0))

        saved = tk.Frame(footer, bg=COLORS["sidebar"])
        saved.pack(fill=tk.X, pady=(16, 0))
        tk.Label(saved, text="●", bg=COLORS["sidebar"], fg=COLORS["green"], font=font(9)).pack(side=tk.LEFT)
        tk.Label(saved, text="Saved to inventory.db", bg=COLORS["sidebar"], fg=COLORS["muted"], font=font(9)).pack(side=tk.LEFT, padx=(6, 0))

    def draw_gradient_square(self, canvas, size, start, end):
        r1, g1, b1 = canvas.winfo_rgb(start)
        r2, g2, b2 = canvas.winfo_rgb(end)
        for i in range(size):
            ratio = i / max(size - 1, 1)
            color = "#%02x%02x%02x" % (
                int((r1 + (r2 - r1) * ratio) / 256),
                int((g1 + (g2 - g1) * ratio) / 256),
                int((b1 + (b2 - b1) * ratio) / 256),
            )
            canvas.create_line(i, 0, 0, i, fill=color)
            canvas.create_line(size - 1, i, i, size - 1, fill=color)

    def build_heading(self, parent):
        heading = tk.Frame(parent, bg=COLORS["page"])
        heading.pack(fill=tk.X)

        left = tk.Frame(heading, bg=COLORS["page"])
        left.pack(side=tk.LEFT)

        tk.Label(
            left,
            text="Product Inventory",
            bg=COLORS["page"],
            fg=COLORS["text"],
            font=font(20, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            left,
            text="Add, view, change, and delete the products in your store.",
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=font(10),
        ).pack(anchor=tk.W, pady=(2, 0))

        right = tk.Frame(heading, bg=COLORS["page"])
        right.pack(side=tk.RIGHT)

        FlatButton(
            right,
            "↻  Refresh",
            self.refresh_data,
            COLORS["card_high"],
            COLORS["text"],
            COLORS["line_high"],
        ).pack(side=tk.RIGHT)

        search_box = tk.Frame(right, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_box.pack(side=tk.RIGHT, padx=(0, 10))
        tk.Label(search_box, text="⌕", bg=COLORS["input"], fg=COLORS["muted"], font=font(12)).pack(side=tk.LEFT, padx=(10, 2))
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            width=28,
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=font(10),
        )
        self.search_entry.pack(side=tk.LEFT, ipady=8, padx=(2, 12))
        self.add_placeholder(self.search_entry, self.search_var, "Search products or categories")
        self.search_entry.bind("<FocusIn>", lambda e: search_box.configure(highlightbackground=COLORS["primary"]), add="+")
        self.search_entry.bind("<FocusOut>", lambda e: search_box.configure(highlightbackground=COLORS["line"]), add="+")

    def add_placeholder(self, entry, variable, text):
        """Show grey hint text inside an empty entry box."""
        hint = tk.Label(entry, text=text, bg=COLORS["input"], fg=COLORS["faint"], font=font(10), cursor="xterm")

        def update(*args):
            if variable.get() or entry.focus_get() == entry:
                hint.place_forget()
            else:
                hint.place(x=0, rely=0.5, anchor=tk.W)

        hint.bind("<Button-1>", lambda e: entry.focus_set())
        entry.bind("<FocusIn>", update, add="+")
        entry.bind("<FocusOut>", update, add="+")
        variable.trace_add("write", update)
        update()

    def build_dashboard(self, parent):
        dashboard = tk.Frame(parent, bg=COLORS["page"])
        dashboard.pack(fill=tk.X, pady=(16, 0))
        for column in range(4):
            dashboard.columnconfigure(column, weight=1, uniform="cards")

        cards = [
            ("TOTAL PRODUCTS", self.total_products_var, "items saved", "▦", COLORS["primary"], COLORS["primary_soft"]),
            ("TOTAL STOCK", self.total_stock_units_var, "pieces on hand", "▤", COLORS["cyan"], COLORS["cyan_soft"]),
            ("LOW STOCK", self.low_stock_products_var, f"below {database.LOW_STOCK_THRESHOLD} pieces", "▲", COLORS["amber"], COLORS["amber_soft"]),
            ("TOTAL VALUE", self.total_value_var, "quantity × price", "₱", COLORS["green"], COLORS["green_soft"]),
        ]

        for index, card in enumerate(cards):
            self.create_summary_card(dashboard, index, *card)

    def create_summary_card(self, parent, column, title, value_var, note, icon, accent, accent_soft):
        outer = tk.Frame(parent, bg=COLORS["line"])
        outer.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 14, 0))

        tk.Frame(outer, bg=accent, height=3).pack(fill=tk.X)

        card = tk.Frame(outer, bg=COLORS["card"], padx=18, pady=10)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

        top = tk.Frame(card, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text=title, bg=COLORS["card"], fg=COLORS["muted"], font=font(8, "bold")).pack(side=tk.LEFT)
        tk.Label(top, text=icon, bg=accent_soft, fg=accent, font=font(11, "bold"), width=2, pady=2).pack(side=tk.RIGHT)

        tk.Label(card, textvariable=value_var, bg=COLORS["card"], fg=COLORS["text"], font=mono(17)).pack(anchor=tk.W, pady=(4, 0))
        tk.Label(card, text=note, bg=COLORS["card"], fg=accent, font=font(9)).pack(anchor=tk.W, pady=(2, 0))

    def make_card(self, parent):
        outer = tk.Frame(parent, bg=COLORS["line"])
        inner = tk.Frame(outer, bg=COLORS["card"], padx=20, pady=18)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def build_form(self, parent):
        outer, form = self.make_card(parent)
        outer.grid(row=0, column=0, sticky="ns", padx=(0, 18))

        header = tk.Frame(form, bg=COLORS["card"])
        header.pack(fill=tk.X)
        tk.Label(header, textvariable=self.form_title_var, bg=COLORS["card"], fg=COLORS["text"], font=font(14, "bold")).pack(side=tk.LEFT)
        self.mode_badge = tk.Label(header, bg=COLORS["primary_soft"], fg=COLORS["primary_hover"], font=font(8, "bold"), padx=8, pady=2)
        self.mode_badge.pack(side=tk.RIGHT)
        tk.Label(form, textvariable=self.form_note_var, bg=COLORS["card"], fg=COLORS["muted"], font=font(9)).pack(anchor=tk.W, pady=(2, 4))

        self.name_entry = self.create_input(form, "Product Name", self.product_name_var, width=26)
        self.create_category_input(form)

        numbers = tk.Frame(form, bg=COLORS["card"])
        numbers.pack(fill=tk.X)
        numbers.columnconfigure((0, 1), weight=1, uniform="numbers")
        quantity_box = tk.Frame(numbers, bg=COLORS["card"])
        quantity_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        price_box = tk.Frame(numbers, bg=COLORS["card"])
        price_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.quantity_entry = self.create_input(quantity_box, "Quantity", self.quantity_var, width=10)
        self.price_entry = self.create_input(price_box, "Price Each (Php)", self.unit_price_var, width=10)

        total_box = tk.Frame(form, bg=COLORS["primary_soft"], padx=14, pady=10)
        total_box.pack(fill=tk.X, pady=(14, 0))
        tk.Label(total_box, text="AMOUNT", bg=COLORS["primary_soft"], fg=COLORS["primary_hover"], font=font(8, "bold")).pack(side=tk.LEFT)
        tk.Label(total_box, textvariable=self.item_total_var, bg=COLORS["primary_soft"], fg="#ffffff", font=mono(14)).pack(side=tk.RIGHT)

        tk.Label(
            form,
            textvariable=self.error_var,
            bg=COLORS["card"],
            fg=COLORS["red"],
            font=font(9, "bold"),
            wraplength=280,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 4))

        buttons = tk.Frame(form, bg=COLORS["card"])
        buttons.pack(fill=tk.X, side=tk.BOTTOM)
        buttons.columnconfigure((0, 1, 2), weight=1, uniform="buttons")

        self.add_button = FlatButton(buttons, "+  Add Product", self.add_product, COLORS["primary"], "#ffffff", COLORS["primary_hover"], pady=11)
        self.add_button.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.update_button = FlatButton(buttons, "✎ Update", self.update_product, COLORS["cyan_soft"], COLORS["cyan"], "#14404b", padx=6)
        self.update_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self.delete_button = FlatButton(buttons, "✕ Delete", self.delete_product, COLORS["red_soft"], COLORS["red"], "#4d1e21", padx=6)
        self.delete_button.grid(row=1, column=1, sticky="ew", padx=4)
        FlatButton(buttons, "Clear", self.clear_fields, COLORS["card_high"], COLORS["muted"], COLORS["line_high"], padx=6).grid(
            row=1, column=2, sticky="ew", padx=(4, 0)
        )

    def create_input(self, parent, label, variable, width=20):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        tk.Label(wrapper, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=font(9, "bold")).pack(anchor=tk.W)
        entry = tk.Entry(
            wrapper,
            textvariable=variable,
            width=width,
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["primary"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["primary"],
            font=font(10),
        )
        entry.pack(fill=tk.X, pady=(4, 0), ipady=6, ipadx=8)
        entry.bind("<Return>", lambda event: self.save_from_keyboard())
        return entry

    def create_category_input(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        tk.Label(wrapper, text="Category", bg=COLORS["card"], fg=COLORS["muted"], font=font(9, "bold")).pack(anchor=tk.W)
        combo = ttk.Combobox(
            wrapper,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="normal",
            width=24,
            font=font(10),
        )
        combo.pack(fill=tk.X, pady=(5, 0), ipady=1)
        combo.bind("<Return>", lambda event: self.save_from_keyboard())

    def build_table(self, parent):
        outer, table_card = self.make_card(parent)
        outer.grid(row=0, column=1, sticky="nsew")
        table_card.rowconfigure(1, weight=1)
        table_card.columnconfigure(0, weight=1)

        header = tk.Frame(table_card, bg=COLORS["card"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew")

        tk.Label(header, text="Product List", bg=COLORS["card"], fg=COLORS["text"], font=font(14, "bold")).pack(side=tk.LEFT)
        tk.Label(header, textvariable=self.list_count_var, bg=COLORS["card_high"], fg=COLORS["muted"], font=font(8, "bold"), padx=8, pady=2).pack(
            side=tk.LEFT, padx=(10, 0)
        )
        tk.Label(header, text="Click a product to edit it  ·  click a heading to sort", bg=COLORS["card"], fg=COLORS["faint"], font=font(9)).pack(
            side=tk.RIGHT
        )

        columns = tuple(TABLE_COLUMNS)
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.heading(column, text=heading, anchor=anchor, command=lambda key=sort_key: self.sort_by(key))
            self.tree.column(column, width=width, minwidth=40, anchor=anchor, stretch=False)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(14, 0))

        self.empty_label = tk.Label(table_card, bg=COLORS["card"], fg=COLORS["muted"], font=font(11), justify=tk.CENTER)

        self.tree.tag_configure("even", background=COLORS["card"])
        self.tree.tag_configure("odd", background=COLORS["row_alt"])
        self.tree.tag_configure("low", foreground=COLORS["amber"])
        self.tree.tag_configure("out", foreground=COLORS["red"])

        self.tree.bind("<<TreeviewSelect>>", self.load_selected_product)
        self.tree.bind("<Delete>", lambda event: self.delete_product())
        self.tree.bind("<Configure>", self.fit_columns)

    def fit_columns(self, event):
        """Stretch or shrink the columns so the table always fits without side scrolling."""
        base_total = sum(width for heading, width, anchor, sort_key in TABLE_COLUMNS.values())
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.column(column, width=int(width * event.width / base_total))

    def bind_shortcuts(self):
        self.root.bind("<Escape>", lambda event: self.clear_fields())
        self.root.bind("<Control-f>", lambda event: self.search_entry.focus_set())
        self.root.bind("<Control-F>", lambda event: self.search_entry.focus_set())

    # ---------------------------------------------------------------- feedback

    def show_toast(self, message, kind="success"):
        accent = {"success": COLORS["green"], "info": COLORS["cyan"], "error": COLORS["red"]}[kind]
        icon = {"success": "✔", "info": "ℹ", "error": "⚠"}[kind]
        self.toast.configure(text=f"{icon}   {message}", fg=accent, highlightthickness=1, highlightbackground=accent)
        self.toast.place(relx=1.0, rely=1.0, x=-28, y=-24, anchor=tk.SE)
        self.toast.lift()

        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(3200, self.toast.place_forget)

    def show_error(self, message, widget=None):
        self.error_var.set(f"⚠  {message}")
        if widget is not None:
            widget.focus_set()

    def set_edit_mode(self, editing):
        self.update_button.set_enabled(editing)
        self.delete_button.set_enabled(editing)
        if editing:
            self.form_title_var.set("Edit Product")
            self.form_note_var.set("Change the details, then press Update.")
            self.mode_badge.configure(text=f"P{self.selected_product_id:03d}", bg=COLORS["cyan_soft"], fg=COLORS["cyan"])
        else:
            self.form_title_var.set("New Product")
            self.form_note_var.set("Fill this out to save a product.")
            self.mode_badge.configure(text="NEW", bg=COLORS["primary_soft"], fg=COLORS["primary_hover"])

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
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        if result == "restocked":
            self.show_toast("Same product already exists, so its quantity was increased.", "info")
        else:
            self.show_toast("Product added successfully.")

    def update_product(self):
        if self.selected_product_id is None:
            self.show_error("Please select a product to update.")
            return

        values = self.validate_inputs()
        if values is None:
            return

        try:
            database.update_product(self.selected_product_id, *values)
        except sqlite3.DatabaseError:
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        self.show_toast("Product updated successfully.")

    def delete_product(self):
        if self.selected_product_id is None:
            self.show_error("Please select a product to delete.")
            return

        confirmed = messagebox.askyesno(
            "Delete Product",
            f"Are you sure you want to delete \"{self.product_name_var.get()}\"?",
        )
        if not confirmed:
            return

        try:
            database.delete_product(self.selected_product_id)
        except sqlite3.DatabaseError:
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
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

    def load_selected_product(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0]
        if int(item_id) == self.selected_product_id:
            return
        values = self.tree.item(item_id, "values")

        self.selected_product_id = int(item_id)
        self.product_name_var.set(values[1])
        self.category_var.set(values[2])
        self.quantity_var.set(values[3])
        self.unit_price_var.set(values[4].replace("Php ", "").replace(",", ""))
        self.error_var.set("")
        self.update_item_total()
        self.set_edit_mode(True)

    def update_item_total(self, *args):
        try:
            quantity = int(self.quantity_var.get() or 0)
            price = float(self.unit_price_var.get() or 0)
        except ValueError:
            self.item_total_var.set("Php 0.00")
            return

        self.item_total_var.set(f"Php {quantity * price:,.2f}")

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
                arrow = "  ▼" if self.sort_reverse else "  ▲"
            self.tree.heading(column, text=heading + arrow)

    def refresh_data(self):
        self.products = [
            dict(product, total=product["quantity"] * product["unit_price"]) for product in database.get_products()
        ]
        self.render_table()

        totals = database.get_dashboard_totals()
        self.total_products_var.set(f"{totals['total_products']:,}")
        self.total_stock_units_var.set(f"{totals['total_stock_units']:,}")
        self.low_stock_products_var.set(f"{totals['low_stock_products']:,}")
        self.total_value_var.set(f"Php {totals['total_value']:,.2f}")

    def render_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip().lower()
        products = [
            product
            for product in self.products
            if search in product["product_name"].lower() or search in product["category"].lower()
        ]

        def sort_value(product):
            value = product[self.sort_key]
            return value.lower() if isinstance(value, str) else value

        products.sort(key=sort_value, reverse=self.sort_reverse)

        for index, product in enumerate(products):
            product_id = product["product_id"]
            quantity = product["quantity"]

            if quantity == 0:
                status, status_tag = "● Out", "out"
            elif quantity < database.LOW_STOCK_THRESHOLD:
                status, status_tag = "● Low", "low"
            else:
                status, status_tag = "● In stock", None

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
                    quantity,
                    f"Php {product['unit_price']:,.2f}",
                    f"Php {product['total']:,.2f}",
                    status,
                ),
                tags=tuple(tags),
            )

        if self.selected_product_id is not None and self.tree.exists(str(self.selected_product_id)):
            self.tree.selection_set(str(self.selected_product_id))

        self.update_sort_arrows()

        if len(products) == len(self.products):
            self.list_count_var.set(f"{len(products)} items")
        else:
            self.list_count_var.set(f"{len(products)} of {len(self.products)}")

        if products:
            self.empty_label.place_forget()
        else:
            if self.products:
                self.empty_label.configure(text="No products match your search.")
            else:
                self.empty_label.configure(text="No products yet.\nAdd your first product using the form on the left.")
            self.empty_label.place(relx=0.5, rely=0.55, anchor=tk.CENTER)


def main():
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
