import sqlite3
import sys
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import messagebox, ttk

import auth
import database
import theme
from auth_screen import AuthScreen
from admin_page import AdminPage
from profile_page import ProfilePage, draw_avatar, nice_time, role_badge
from theme import COLORS, FlatButton
from validation import ValidationError, parse_price, parse_quantity, validate_product


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

TABLE_COLUMNS_BY_KEY = {sort_key: heading for heading, width, anchor, sort_key in TABLE_COLUMNS.values() if sort_key != "quantity" or heading == "Stock"}

LOG_COLORS = {
    "START": "primary", "ADD": "green", "RESTOCK": "green", "UPDATE": "primary", "DELETE": "red", "ALERT": "amber",
    "ERROR": "red", "THEME": "muted", "SIGN IN": "secondary", "SIGN UP": "secondary", "SIGN OUT": "muted",
    "PROFILE": "amber", "PASSWORD": "amber", "ROLE": "amber", "ACCOUNT": "amber",
}

PAGE_TITLES = {"inventory": "Product Inventory System", "profile": "My Dashboard", "admin": "Admin Dashboard"}
PAGE_DESCRIPTIONS = {
    "inventory": "Product records, stock totals, and daily inventory work",
    "profile": "Personal only - profile, password, photo, and your own activity",
    "admin": "Admin only - approvals, users, roles, resets, and system-wide activity",
}

WINDOW_TITLE = "Product Inventory System"

# parse_quantity and parse_price are imported above so older code and tests can keep using main.parse_price.
__all__ = ["InventoryApp", "main", "parse_price", "parse_quantity"]


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


def log_time(created_at):
    """Show today's saved actions as 14:05:09 and older ones as Nov 15 14:05."""
    try:
        moment = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return "--:--"
    if moment.date() == datetime.now().date():
        return moment.strftime("%H:%M:%S")
    return moment.strftime("%b %d %H:%M")


class InventoryApp:
    def __init__(self, root, user, on_sign_out=None):
        self.root = root
        self.user = user
        self.on_sign_out = on_sign_out
        self.root.title(f"{WINDOW_TITLE} - {user.full_name}")

        self.selected_product_id = None
        self.products = []
        self.category_filter = "All"
        self.sort_key = "product_id"
        self.sort_reverse = True
        self.toast_job = None
        self.placeholder_trace = None
        self.form_traces = []
        self.health_ratio = 0.0
        self.started_at = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.log_entries = []
        self.viewer = None
        self.page = "inventory"
        self.page_user_id = None
        self.page_view = None
        self.nav_widgets = {}

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
        self.out_stock_unit_var = tk.StringVar(value="add stock")
        self.sidebar_records_var = tk.StringVar()
        self.health_var = tk.StringVar(value="0%")
        self.footer_var = tk.StringVar()
        self.db_size_var = tk.StringVar(value="0 KB")
        self.index_var = tk.StringVar()

        self.log_entries = [
            (log_time(row["created_at"]), row["action"], row["details"], row["username"])
            for row in database.get_recent_activity(40)
        ]

        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.bind_shortcuts()
        self.refresh_data()
        self.set_edit_mode(False)

        self.quantity_var.trace_add("write", self.update_item_total)
        self.unit_price_var.trace_add("write", self.update_item_total)
        self.search_var.trace_add("write", lambda *args: self.render_table())

        self.log("START", f"Welcome, {user.full_name}. {len(self.products)} product(s) loaded from inventory.db.")
        low = [p for p in self.products if p["quantity"] < database.LOW_STOCK_THRESHOLD]
        if low:
            self.log("ALERT", f"{len(low)} product(s) below {database.LOW_STOCK_THRESHOLD} pieces. Please add stock.")

    # ------------------------------------------------------------------ layout

    def build_interface(self):
        self.build_sidebar()

        body = tk.Frame(self.root, bg=COLORS["page"])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.body = body
        self.page_view = None
        self.build_header(body)
        self.build_footer(body)

        shell = tk.Frame(body, bg=COLORS["page"], padx=20, pady=14)
        shell.pack(fill=tk.BOTH, expand=True)
        self.shell = shell
        self.build_kpis(shell)

        main = tk.Frame(shell, bg=COLORS["page"])
        main.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=COLORS["page"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(main, bg=COLORS["page"], width=318)
        right.grid(row=0, column=1, sticky="ns")
        right.pack_propagate(False)

        self.build_bottom_row(left)
        self.build_table(left)
        self.build_form(right)

        self.toast = tk.Frame(self.root, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["line_high"])
        self.toast_stripe = tk.Frame(self.toast, width=3, bg=COLORS["primary"])
        self.toast_stripe.pack(side=tk.LEFT, fill=tk.Y)
        self.toast_label = tk.Label(self.toast, bg=COLORS["card"], fg=COLORS["text"], font=sans(10, "bold"), padx=14, pady=9)
        self.toast_label.pack(side=tk.LEFT)

    # small building blocks

    def panel(self, parent, padx=16, pady=14, bg=None):
        """A dark card with a thin border."""
        outer = tk.Frame(parent, bg=COLORS["line"])
        inner = tk.Frame(outer, bg=bg or COLORS["card"], padx=padx, pady=pady)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def caps(self, parent, text, color=None, bg=None, size=7, weight="bold", **options):
        """Small grey label used above values and boxes."""
        return tk.Label(parent, text=text, bg=bg or COLORS["card"], fg=color or COLORS["muted"], font=sans(size + 1, weight), **options)

    def kbd(self, parent, text, bg=None):
        """A small keyboard key hint, like [Ctrl+F]."""
        return tk.Label(
            parent, text=text, bg=COLORS["card_high"], fg=COLORS["muted"], font=sans(8), padx=4,
            highlightthickness=1, highlightbackground=COLORS["line_high"],
        )

    # left side bar

    def build_sidebar(self):
        bar = tk.Frame(self.root, bg=COLORS["sidebar"], width=214)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        bar.pack_propagate(False)
        tk.Frame(self.root, bg=COLORS["line"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        brand = tk.Frame(bar, bg=COLORS["sidebar"], padx=16, pady=14)
        brand.pack(fill=tk.X)
        logo = tk.Canvas(brand, width=34, height=34, bg=COLORS["sidebar"], highlightthickness=0)
        logo.pack(side=tk.LEFT)
        logo.create_rectangle(1, 1, 33, 33, fill=COLORS["card_high"], outline=COLORS["primary_line"])
        logo.create_polygon(17, 7, 26, 12, 17, 17, 8, 12, fill=COLORS["primary"], outline="")
        logo.create_polygon(8, 14, 16, 18, 16, 27, 8, 23, fill=COLORS["primary"], outline="")
        logo.create_polygon(26, 14, 18, 18, 18, 27, 26, 23, fill=COLORS["primary_hover"], outline="")
        names = tk.Frame(brand, bg=COLORS["sidebar"])
        names.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(names, text="IM102", bg=COLORS["sidebar"], fg=COLORS["strong"], font=sans(15, "bold")).pack(anchor=tk.W)
        self.caps(names, "Product Inventory", bg=COLORS["sidebar"], size=7, weight="normal").pack(anchor=tk.W)

        strip = tk.Frame(bar, bg=COLORS["card"], padx=14, pady=6)
        strip.pack(fill=tk.X)
        self.caps(strip, "inventory.db", color=COLORS["primary"], size=7).pack(side=tk.LEFT)
        tk.Label(strip, textvariable=self.sidebar_records_var, bg=COLORS["card"], fg=COLORS["primary_hover"], font=sans(8, "bold")).pack(side=tk.RIGHT)

        self.caps(bar, "Menu", bg=COLORS["sidebar"], size=7, padx=16, pady=10).pack(anchor=tk.W, pady=(8, 0))
        menu = [
            ("▦", "Inventory", lambda: self.show_page("inventory"), True),
            ("●", "My Dashboard", lambda: self.show_page("profile"), False),
        ]
        if self.user.is_admin:
            menu += [
                ("★", "Admin Dashboard", lambda: self.show_page("admin"), False),
                ("⛁", "Database Records", self.open_database_viewer, False),
            ]
        menu += [
            ("+", "New Product", self.start_new_product, False),
            ("☀" if theme.MODE == "dark" else "☾", "Light Mode" if theme.MODE == "dark" else "Dark Mode", self.toggle_theme, False),
        ]
        for icon, text, command, active in menu:
            self.nav_item(bar, icon, text, command, active)

        bottom = tk.Frame(bar, bg=COLORS["sidebar"], padx=12, pady=12)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.build_user_card(bottom)
        box = tk.Frame(bottom, bg=COLORS["card"], padx=10, pady=8, highlightthickness=1, highlightbackground=COLORS["line"])
        box.pack(fill=tk.X, pady=(10, 0))
        row = tk.Frame(box, bg=COLORS["card"])
        row.pack(fill=tk.X)
        self.caps(row, "Database").pack(side=tk.LEFT)
        tk.Label(row, text=f"v{sqlite3.sqlite_version}", bg=COLORS["card"], fg=COLORS["primary_hover"], font=sans(8, "bold")).pack(side=tk.RIGHT)
        row = tk.Frame(box, bg=COLORS["card"])
        row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(row, text="Products in stock", bg=COLORS["card"], fg=COLORS["dim"], font=sans(8)).pack(side=tk.LEFT)
        tk.Label(row, textvariable=self.health_var, bg=COLORS["card"], fg=COLORS["text"], font=sans(8, "bold")).pack(side=tk.RIGHT)
        self.health_bar = tk.Canvas(box, height=4, bg=COLORS["card_top"], highlightthickness=0)
        self.health_bar.pack(fill=tk.X, pady=(5, 0))
        self.health_bar.bind("<Configure>", lambda event: self.draw_health())
        row = tk.Frame(bottom, bg=COLORS["sidebar"])
        row.pack(fill=tk.X, pady=(8, 0))
        self.caps(row, "Product Inventory System", bg=COLORS["sidebar"], weight="normal").pack(side=tk.LEFT)

    def build_user_card(self, parent):
        """Who is signed in, with a Sign Out button."""
        card = tk.Frame(parent, bg=COLORS["card"], padx=10, pady=10, highlightthickness=1, highlightbackground=COLORS["line"], cursor="hand2")
        card.pack(fill=tk.X)
        row = tk.Frame(card, bg=COLORS["card"])
        row.pack(fill=tk.X)
        avatar = tk.Canvas(row, width=34, height=34, bg=COLORS["card"], highlightthickness=0)
        avatar.pack(side=tk.LEFT)
        try:
            photo = database.get_photo(self.user.user_id)
        except sqlite3.DatabaseError:
            photo = None
        draw_avatar(avatar, 34, self.user.full_name, photo)
        names = tk.Frame(row, bg=COLORS["card"])
        names.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)
        full_name = self.user.full_name if len(self.user.full_name) <= 18 else self.user.full_name[:17] + "…"
        full_name_label = tk.Label(names, text=full_name, bg=COLORS["card"], fg=COLORS["strong"], font=sans(9, "bold"), anchor=tk.W, cursor="hand2")
        full_name_label.pack(fill=tk.X)
        line = tk.Frame(names, bg=COLORS["card"])
        line.pack(fill=tk.X)
        username_label = tk.Label(line, text=f"@{self.user.username}", bg=COLORS["card"], fg=COLORS["muted"], font=sans(8), anchor=tk.W, cursor="hand2")
        username_label.pack(side=tk.LEFT)
        badge = role_badge(line, self.user.role)
        badge.configure(cursor="hand2")
        badge.pack(side=tk.LEFT, padx=(6, 0))

        # Tk events do not bubble from child labels to their parent frame. Bind every
        # visible identity element so the whole profile card behaves like one control.
        for widget in (card, row, avatar, names, full_name_label, line, username_label, badge):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda event: self.show_page("profile"))
        FlatButton(
            card, "Sign Out", self.sign_out, COLORS["card_high"], COLORS["dim"], COLORS["red_soft"],
            font_size=8, pady=5, border=COLORS["line_high"], hover_fg=COLORS["red"],
        ).pack(fill=tk.X, pady=(10, 0))

    def nav_item(self, parent, icon, text, command, active):
        item = tk.Frame(parent, cursor="hand2")
        item.pack(fill=tk.X, padx=10, pady=1)
        stripe = tk.Frame(item, width=2)
        stripe.pack(side=tk.LEFT, fill=tk.Y)
        icon_label = tk.Label(item, text=icon, width=1, pady=8)
        icon_label.pack(side=tk.LEFT, padx=(4, 4))
        text_label = tk.Label(item, text=text)
        text_label.pack(side=tk.LEFT)
        self.nav_widgets[text] = (item, stripe, icon_label, text_label)
        self.paint_nav(text, active)
        widgets = (item, stripe, icon_label, text_label)

        def hover(inside):
            if getattr(item, "active", False):
                return
            color = COLORS["card"] if inside else COLORS["sidebar"]
            for widget in widgets:
                widget.configure(bg=color)

        for widget in widgets:
            widget.bind("<Button-1>", lambda event: command())
            widget.bind("<Enter>", lambda event: hover(True))
            widget.bind("<Leave>", lambda event: hover(False))

    def paint_nav(self, text, active):
        item, stripe, icon_label, text_label = self.nav_widgets[text]
        item.active = active
        bg = COLORS["card_high"] if active else COLORS["sidebar"]
        for widget in (item, icon_label):
            widget.configure(bg=bg)
        stripe.configure(bg=COLORS["primary"] if active else bg)
        text_label.configure(bg=bg, fg=COLORS["strong"] if active else COLORS["dim"], font=sans(9, "bold" if active else "normal"))

    def show_page(self, page, user_id=None):
        """Switch the main area between Inventory, My Dashboard, Admin Dashboard, and a team member's profile.

        Every page opens inside this window, never in a new one.
        """
        if page == "admin":
            try:
                auth.require_permission(self.user, "manage_accounts")
            except ValidationError:
                page = "profile"
        if user_id == self.user.user_id:
            user_id = None
        if page == "profile" and user_id is not None and not self.user.is_admin:
            user_id = None
        self.page, self.page_user_id = page, user_id

        if self.page_view is not None and self.page_view.frame.winfo_exists():
            self.page_view.frame.destroy()
        self.page_view = None
        if page == "inventory":
            self.shell.pack(fill=tk.BOTH, expand=True)
        else:
            self.shell.pack_forget()
            self.page_view = AdminPage(self.body, self) if page == "admin" else ProfilePage(self.body, self, user_id)
            self.page_view.frame.pack(fill=tk.BOTH, expand=True)

        if page == "profile" and user_id is not None and self.page_view.row is not None:
            title = f"Profile: {self.page_view.row['full_name']}"
            description = "Admin account management - role, status, password reset, and this user's activity"
        else:
            title = PAGE_TITLES[page]
            description = PAGE_DESCRIPTIONS[page]
        self.header_title.configure(text=title)
        self.header_description.configure(text=description)
        self.paint_nav("Inventory", page == "inventory")
        self.paint_nav("My Dashboard", page == "profile" and user_id is None)
        if "Admin Dashboard" in self.nav_widgets:
            self.paint_nav("Admin Dashboard", page == "admin" or (page == "profile" and user_id is not None))

    def on_profile_changed(self, message="Your name was saved."):
        """The user's name or photo changed: update the window title, side menu, and header."""
        self.root.title(f"{WINDOW_TITLE} - {self.user.full_name}")
        def redraw():
            self.rebuild_screen()
            self.show_toast(message)
        self.root.after_idle(redraw)

    def draw_health(self):
        if not hasattr(self, "health_bar") or not self.health_bar.winfo_exists():
            return
        bar = self.health_bar
        bar.delete("all")
        width = max(bar.winfo_width(), 10)
        bar.create_rectangle(0, 0, int(width * self.health_ratio), 4, fill=COLORS["primary"], outline="")

    # top bar and footer

    def build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["header"], padx=20, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(parent, bg=COLORS["line"], height=1).pack(fill=tk.X)

        left = tk.Frame(header, bg=COLORS["header"])
        left.pack(side=tk.LEFT, fill=tk.Y)
        title_group = tk.Frame(left, bg=COLORS["header"])
        title_group.pack(side=tk.LEFT, fill=tk.Y, pady=5)
        self.header_title = tk.Label(
            title_group, text=PAGE_TITLES["inventory"], bg=COLORS["header"], fg=COLORS["strong"],
            font=sans(13, "bold"), anchor=tk.W,
        )
        self.header_title.pack(anchor=tk.W)
        self.header_description = tk.Label(
            title_group, text=PAGE_DESCRIPTIONS["inventory"], bg=COLORS["header"], fg=COLORS["muted"],
            font=sans(7), anchor=tk.W,
        )
        self.header_description.pack(anchor=tk.W)

        pill = tk.Frame(left, bg=COLORS["card_high"], padx=8, pady=3, highlightthickness=1, highlightbackground=COLORS["line_high"])
        pill.pack(side=tk.LEFT, padx=(16, 0))
        tk.Label(pill, text="●", bg=COLORS["card_high"], fg=COLORS["primary"], font=sans(8)).pack(side=tk.LEFT)
        tk.Label(pill, text=f" Signed in as @{self.user.username}", bg=COLORS["card_high"], fg=COLORS["text"], font=sans(8)).pack(side=tk.LEFT)

        right = tk.Frame(header, bg=COLORS["header"])
        right.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(
            right, "New Product", self.start_new_product, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=6, border=COLORS["button"],
        ).pack(side=tk.RIGHT, pady=12)
        if self.user.is_admin:
            FlatButton(
                right, "Database Records", self.open_database_viewer, COLORS["card_high"], COLORS["text"], COLORS["card_top"],
                font_size=8, pady=6, border=COLORS["line_high"], hover_fg=COLORS["strong"],
            ).pack(side=tk.RIGHT, padx=(0, 8), pady=12)
        toggle_text = "Light Mode" if theme.MODE == "dark" else "Dark Mode"
        FlatButton(
            right, toggle_text, self.toggle_theme, COLORS["card_high"], COLORS["text"], COLORS["card_top"],
            font_size=8, pady=6, border=COLORS["line_high"], hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=12)

    def build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["sidebar"], padx=20, height=30)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        footer.pack_propagate(False)
        tk.Frame(parent, bg=COLORS["line"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(footer, textvariable=self.footer_var, bg=COLORS["sidebar"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT)
        shortcuts = tk.Frame(footer, bg=COLORS["sidebar"])
        shortcuts.pack(side=tk.RIGHT)
        self.caps(shortcuts, "Shortcuts:", bg=COLORS["sidebar"]).pack(side=tk.LEFT, padx=(0, 4))
        for key, action in (("Enter", "Save"), ("Esc", "Clear"), ("Del", "Delete"), ("Ctrl+F", "Search"), ("Ctrl+L", "Theme")):
            self.kbd(shortcuts, key).pack(side=tk.LEFT, padx=(8, 3))
            tk.Label(shortcuts, text=action, bg=COLORS["sidebar"], fg=COLORS["dim"], font=sans(8)).pack(side=tk.LEFT)

    # summary cards

    def build_kpis(self, parent):
        strip = tk.Frame(parent, bg=COLORS["page"])
        strip.pack(fill=tk.X)
        for column in range(5):
            strip.columnconfigure(column, weight=1, uniform="kpi")

        cards = [
            ("Total Inventory Value", "₱", "secondary", self.total_value_var, None, "Quantity × unit price, all products", "muted"),
            ("Total Products", "▦", "primary", self.total_products_var, self.total_units_var, "● Saved in inventory.db", "primary"),
            ("Low Stock", "▲", "amber", self.low_stock_var, self.low_stock_unit_var, self.low_stock_detail_var, "amber"),
            ("Out of Stock", "⊘", "red", self.out_stock_var, self.out_stock_unit_var, self.out_stock_detail_var, "red"),
            ("Database File", "⛁", "primary", self.db_size_var, None, "3 tables: products, users, activity", "muted"),
        ]

        for index, (label, icon, color, value, extra, note, note_color) in enumerate(cards):
            outer, card = self.panel(strip, padx=14, pady=10)
            outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))

            top = tk.Frame(card, bg=COLORS["card"])
            top.pack(fill=tk.X)
            self.caps(top, label).pack(side=tk.LEFT)

            row = tk.Frame(card, bg=COLORS["card"])
            row.pack(fill=tk.X, pady=(2, 0))
            value_color = COLORS["strong"] if color in ("primary", "secondary") else COLORS[color]
            tk.Label(row, textvariable=value, bg=COLORS["card"], fg=value_color, font=sans(17, "bold")).pack(side=tk.LEFT)
            if extra is not None:
                tk.Label(row, textvariable=extra, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT, padx=(6, 0), pady=(7, 0))

            note_options = {"textvariable": note} if isinstance(note, tk.StringVar) else {"text": note}
            tk.Label(card, bg=COLORS["card"], fg=COLORS[note_color], font=sans(8), anchor=tk.W, **note_options).pack(fill=tk.X)

    # product table

    def build_table(self, parent):
        outer, card = self.panel(parent, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(card, bg=COLORS["card"], padx=16, pady=10)
        top.pack(fill=tk.X)
        tk.Label(top, text="Product List", bg=COLORS["card"], fg=COLORS["strong"], font=sans(14, "bold")).pack(side=tk.LEFT)
        tk.Label(
            top, textvariable=self.row_count_var, bg=COLORS["primary_soft"], fg=COLORS["primary"], font=sans(8, "bold"), padx=6, pady=2,
        ).pack(side=tk.LEFT, padx=(10, 0))

        search_box = tk.Frame(top, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line_high"])
        search_box.pack(side=tk.RIGHT)
        tk.Label(search_box, text="⌕", bg=COLORS["input"], fg=COLORS["muted"], font=sans(11)).pack(side=tk.LEFT, padx=(8, 0))
        self.search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            width=28,
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["primary"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=sans(9),
        )
        self.search_entry.pack(side=tk.LEFT, ipady=5, padx=(4, 6))
        self.kbd(search_box, "Ctrl+F").pack(side=tk.LEFT, padx=(0, 6))
        self.add_placeholder(self.search_entry, self.search_var, "Search by ID, name, or category...")
        self.search_entry.bind("<FocusIn>", lambda e: search_box.configure(highlightbackground=COLORS["primary"]), add="+")
        self.search_entry.bind("<FocusOut>", lambda e: search_box.configure(highlightbackground=COLORS["line_high"]), add="+")

        self.chip_frame = tk.Frame(card, bg=COLORS["card"], padx=16)
        self.chip_frame.pack(fill=tk.X, pady=(0, 10))

        table_area = tk.Frame(card, bg=COLORS["card"])
        table_area.pack(fill=tk.BOTH, expand=True)
        table_area.rowconfigure(0, weight=1)
        table_area.columnconfigure(0, weight=1)

        columns = tuple(TABLE_COLUMNS)
        self.tree = ttk.Treeview(table_area, columns=columns, show="headings", selectmode="browse")
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            command = (lambda key=sort_key: self.sort_by(key)) if sort_key else ""
            self.tree.heading(column, text=heading, anchor=anchor, command=command)
            self.tree.column(column, width=width, minwidth=40, anchor=anchor, stretch=False)

        scrollbar = ttk.Scrollbar(table_area, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = tk.Frame(card, bg=COLORS["card_high"], padx=16, pady=5)
        footer.pack(fill=tk.X)
        tk.Label(footer, textvariable=self.index_var, bg=COLORS["card_high"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT)
        self.caps(footer, "Click a row to edit it  ·  Click a heading to sort", color=COLORS["primary"], bg=COLORS["card_high"]).pack(side=tk.RIGHT)

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
                f"{category} ({count})",
                lambda value=category: self.set_category_filter(value),
                COLORS["primary"] if active else COLORS["card_high"],
                COLORS["button_text"] if active else COLORS["dim"],
                COLORS["primary_hover"] if active else COLORS["card_top"],
                font_size=7,
                padx=9,
                pady=4,
                border=COLORS["primary"] if active else COLORS["line"],
                hover_fg=COLORS["button_text"] if active else COLORS["strong"],
            )
            chip.pack(side=tk.LEFT, padx=(0, 6))

    def add_placeholder(self, entry, variable, text):
        """Show grey hint text inside an empty entry box."""
        hint = tk.Label(entry, text=text, bg=COLORS["input"], fg=COLORS["faint"], font=sans(9), cursor="xterm")

        def update(*args):
            if variable.get() or entry.focus_get() == entry:
                hint.place_forget()
            else:
                hint.place(x=0, rely=0.5, anchor=tk.W)

        hint.bind("<Button-1>", lambda e: entry.focus_set())
        entry.bind("<FocusIn>", update, add="+")
        entry.bind("<FocusOut>", update, add="+")
        trace = variable.trace_add("write", update)
        if variable is self.search_var:
            self.placeholder_trace = trace
        else:
            self.form_traces.append((variable, trace))
        update()

    def fit_columns(self, event):
        """Stretch or shrink the columns so the table always fits without side scrolling."""
        base_total = sum(width for heading, width, anchor, sort_key in TABLE_COLUMNS.values())
        for column, (heading, width, anchor, sort_key) in TABLE_COLUMNS.items():
            self.tree.column(column, width=int(width * event.width / base_total))

    # activity log and product inspector

    def build_bottom_row(self, parent):
        row = tk.Frame(parent, bg=COLORS["page"], height=176)
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))
        row.grid_propagate(False)
        row.columnconfigure(0, weight=1, uniform="bottom")
        row.columnconfigure(1, weight=1, uniform="bottom")
        row.rowconfigure(0, weight=1)

        # Activity log
        outer, log_card = self.panel(row, padx=14, pady=10)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        top = tk.Frame(log_card, bg=COLORS["card"])
        top.pack(fill=tk.X)
        self.caps(top, "Activity Log", color=COLORS["primary"], size=8).pack(side=tk.LEFT)
        self.caps(top, "Saved in inventory.db", weight="normal").pack(side=tk.RIGHT)

        self.log_box = tk.Text(
            log_card,
            height=4,
            bg=COLORS["card"],
            fg=COLORS["dim"],
            font=sans(9),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=6,
            wrap=tk.WORD,
            cursor="arrow",
            spacing1=1,
            spacing3=1,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)
        for name in set(LOG_COLORS.values()):
            self.log_box.tag_configure(name, foreground=COLORS[name], font=sans(9, "bold"))
        self.log_box.tag_configure("time", foreground=COLORS["faint"], font=sans(9))
        self.log_box.configure(state=tk.DISABLED)
        for entry in self.log_entries:
            self.write_log_line(*entry)

        # Product inspector
        outer, inspector = self.panel(row, padx=14, pady=10)
        outer.grid(row=0, column=1, sticky="nsew")
        top = tk.Frame(inspector, bg=COLORS["card"])
        top.pack(fill=tk.X)
        self.caps(top, "Product Details", color=COLORS["primary"], size=8).pack(side=tk.LEFT)
        self.inspect_pill = tk.Label(top, bg=COLORS["card"], font=sans(8, "bold"), padx=6, pady=1)
        self.inspect_pill.pack(side=tk.RIGHT)

        self.ins_name = tk.Label(inspector, bg=COLORS["card"], fg=COLORS["strong"], font=sans(13, "bold"), anchor=tk.W)
        self.ins_name.pack(fill=tk.X, pady=(6, 0))
        self.ins_id = tk.Label(inspector, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8), anchor=tk.W)
        self.ins_id.pack(fill=tk.X)

        tiles = tk.Frame(inspector, bg=COLORS["card"])
        tiles.pack(fill=tk.X, pady=(6, 0))
        self.ins_tiles = {}
        for column, name in enumerate(("Stock", "Unit Price", "Total Value", "Status")):
            tiles.columnconfigure(column, weight=1, uniform="tiles")
            tile = tk.Frame(tiles, bg=COLORS["card_high"], padx=7, pady=4)
            tile.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 4, 0))
            self.caps(tile, name, bg=COLORS["card_high"], size=6, weight="normal").pack(anchor=tk.W)
            value = tk.Label(tile, text="--", bg=COLORS["card_high"], fg=COLORS["text"], font=sans(9, "bold"), anchor=tk.W)
            value.pack(anchor=tk.W)
            self.ins_tiles[name] = value

        self.stock_meter = tk.Canvas(inspector, height=12, bg=COLORS["card"], highlightthickness=0)
        self.stock_meter.pack(fill=tk.X, pady=(6, 0))
        self.stock_meter.bind("<Configure>", lambda event: self.update_inspector())

    # product form

    def build_form(self, parent):
        outer, form = self.panel(parent, padx=16, pady=14)
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(form, bg=COLORS["card"])
        header.pack(fill=tk.X)
        self.mode_badge = tk.Label(header, font=sans(8, "bold"), padx=6, pady=1)
        self.mode_badge.pack(side=tk.RIGHT, anchor=tk.N, pady=(4, 0))
        self.form_title = tk.Label(header, text="Add a Product", bg=COLORS["card"], fg=COLORS["strong"], font=sans(15, "bold"))
        self.form_title.pack(anchor=tk.W)
        self.form_subtitle = tk.Label(form, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8), anchor=tk.W, justify=tk.LEFT, wraplength=280)
        self.form_subtitle.pack(fill=tk.X)

        self.name_entry = self.create_input(form, "Product Name", self.product_name_var, required=True, hint="e.g. Bottled Water 500ml")
        self.create_category_input(form)

        numbers = tk.Frame(form, bg=COLORS["card"])
        numbers.pack(fill=tk.X)
        numbers.columnconfigure((0, 1), weight=1, uniform="numbers")
        quantity_box = tk.Frame(numbers, bg=COLORS["card"])
        quantity_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        price_box = tk.Frame(numbers, bg=COLORS["card"])
        price_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.quantity_entry = self.create_input(quantity_box, "Quantity (pcs)", self.quantity_var, width=8, hint="0")
        self.price_entry = self.create_input(price_box, "Unit Price (PHP)", self.unit_price_var, width=8, prefix="₱", hint="0.00")

        total_box = tk.Frame(form, bg=COLORS["card_high"], padx=12, pady=8, highlightthickness=1, highlightbackground=COLORS["line_high"])
        total_box.pack(fill=tk.X, pady=(12, 0))
        labels = tk.Frame(total_box, bg=COLORS["card_high"])
        labels.pack(side=tk.LEFT)
        self.caps(labels, "Total Amount", bg=COLORS["card_high"]).pack(anchor=tk.W)
        tk.Label(labels, text="Quantity × Unit Price", bg=COLORS["card_high"], fg=COLORS["dim"], font=sans(8)).pack(anchor=tk.W)
        tk.Label(total_box, textvariable=self.item_total_var, bg=COLORS["card_high"], fg=COLORS["secondary"], font=sans(16, "bold")).pack(side=tk.RIGHT)

        self.error_label = tk.Label(
            form,
            textvariable=self.error_var,
            bg=COLORS["red_soft"],
            fg=COLORS["red"],
            font=sans(9, "bold"),
            wraplength=270,
            justify=tk.LEFT,
            anchor=tk.W,
            padx=10,
            pady=6,
        )
        self.error_var.trace_add("write", self.show_or_hide_error)

        note_text = "Every change is saved with your name." if self.user.is_admin else "Only an admin can delete products."
        note = tk.Label(form, text=note_text, bg=COLORS["card"], fg=COLORS["faint"], font=sans(8), anchor=tk.W)
        note.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        buttons = tk.Frame(form, bg=COLORS["card"])
        buttons.pack(fill=tk.X, side=tk.BOTTOM)
        buttons.columnconfigure((0, 1), weight=1, uniform="buttons")

        self.add_button = FlatButton(
            buttons, "Add Product", self.add_product, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=9, pady=9, border=COLORS["button"],
        )
        self.add_button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.update_button = FlatButton(
            buttons, "Update", self.update_product, COLORS["card_high"], COLORS["strong"], COLORS["card_top"], font_size=8, border=COLORS["line_high"]
        )
        self.update_button.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(0, 6))
        self.delete_button = FlatButton(
            buttons, "Delete", self.delete_product, COLORS["red_soft"], COLORS["red"], COLORS["red_hover"], font_size=8, border=COLORS["red_line"]
        )
        self.delete_button.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(0, 6))
        FlatButton(
            buttons, "Clear Fields", self.clear_fields, COLORS["card"], COLORS["dim"], COLORS["card_high"], font_size=8,
            border=COLORS["line"], hover_fg=COLORS["strong"],
        ).grid(row=2, column=0, columnspan=2, sticky="ew")

    def show_or_hide_error(self, *args):
        if self.error_var.get():
            self.error_label.pack(fill=tk.X, pady=(10, 0))
        else:
            self.error_label.pack_forget()

    def create_input(self, parent, label, variable, width=30, required=False, prefix=None, hint=None):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        top = tk.Frame(wrapper, bg=COLORS["card"])
        top.pack(fill=tk.X)
        self.caps(top, label, color=COLORS["dim"]).pack(side=tk.LEFT)
        if required:
            self.caps(top, "Required", color=COLORS["faint"], weight="normal").pack(side=tk.RIGHT)

        box = tk.Frame(wrapper, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line_high"])
        box.pack(fill=tk.X, pady=(4, 0))
        if prefix:
            tk.Label(box, text=prefix, bg=COLORS["input"], fg=COLORS["muted"], font=sans(10)).pack(side=tk.LEFT, padx=(8, 0))
        entry = tk.Entry(
            box,
            textvariable=variable,
            width=width,
            bg=COLORS["input"],
            fg=COLORS["text"],
            insertbackground=COLORS["primary"],
            selectbackground=COLORS["primary"],
            selectforeground=COLORS["button_text"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=sans(10),
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=8)
        entry.bind("<FocusIn>", lambda e: box.configure(highlightbackground=COLORS["primary"]), add="+")
        entry.bind("<FocusOut>", lambda e: box.configure(highlightbackground=COLORS["line_high"]), add="+")
        entry.bind("<Return>", lambda event: self.save_from_keyboard())
        if hint:
            self.add_placeholder(entry, variable, hint)
        return entry

    def create_category_input(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(10, 0))

        self.caps(wrapper, "Category", color=COLORS["dim"]).pack(anchor=tk.W)
        combo = ttk.Combobox(
            wrapper,
            textvariable=self.category_var,
            values=CATEGORIES,
            state="normal",
            width=28,
            font=sans(10),
        )
        combo.pack(fill=tk.X, pady=(4, 0))
        self.category_entry = combo
        combo.bind("<Return>", lambda event: self.save_from_keyboard())

    def bind_shortcuts(self):
        self.root.bind("<Escape>", lambda event: self.clear_product_form())
        self.root.bind("<Control-f>", lambda event: self.focus_product_search())
        self.root.bind("<Control-F>", lambda event: self.focus_product_search())
        self.root.bind("<Control-l>", lambda event: self.toggle_theme())
        self.root.bind("<Control-L>", lambda event: self.toggle_theme())

    # ---------------------------------------------------------------- feedback

    def show_toast(self, message, kind="success"):
        accent = {"success": COLORS["primary"], "info": COLORS["secondary"], "error": COLORS["red"]}[kind]
        icon = {"success": "✓", "info": "ℹ", "error": "⚠"}[kind]
        self.toast_stripe.configure(bg=accent)
        self.toast_label.configure(text=f"{icon}  {message}", fg=accent)
        self.toast.place(relx=1.0, x=-20, y=66, anchor=tk.NE)
        self.toast.lift()

        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(3200, self.toast.place_forget)

    def log(self, kind, message, save=False):
        """Write a line in the Activity Log. Product changes are also saved with the user's name."""
        who = None
        if save:
            who = self.user.username
            try:
                database.add_activity(self.user.user_id, kind, message)
            except sqlite3.DatabaseError:
                pass  # the change itself was saved; losing one history line should not stop the user
        entry = (datetime.now().strftime("%H:%M:%S"), kind, message, who)
        self.log_entries.append(entry)
        self.log_entries = self.log_entries[-100:]
        self.write_log_line(*entry)

    def write_log_line(self, time_text, kind, message, who=None):
        self.log_box.configure(state=tk.NORMAL)
        if self.log_box.index("end-1c") != "1.0":
            self.log_box.insert(tk.END, "\n")
        self.log_box.insert(tk.END, f"{time_text} ", "time")
        self.log_box.insert(tk.END, f"[{database.action_label(kind)}]", LOG_COLORS.get(kind, "muted"))
        self.log_box.insert(tk.END, f" {message}")
        if who:
            self.log_box.insert(tk.END, f"  · @{who}", "time")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def show_error(self, message, widget=None):
        self.error_var.set(f"⚠  {message}")
        if widget is not None:
            widget.focus_set()

    def set_edit_mode(self, editing):
        self.update_button.set_enabled(editing)
        self.delete_button.set_enabled(editing and self.user.is_admin)
        if editing:
            self.form_title.configure(text="Edit Product")
            self.form_subtitle.configure(text=f"Change the details of P{self.selected_product_id:03d}, then click Update.")
            self.mode_badge.configure(text="Editing", bg=COLORS["amber_soft"], fg=COLORS["amber"])
        else:
            self.form_title.configure(text="Add a Product")
            self.form_subtitle.configure(text="Type the details, or click a row to edit.")
            self.mode_badge.configure(text="New", bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self.update_inspector()

    def update_inspector(self):
        if not hasattr(self, "stock_meter") or not self.stock_meter.winfo_exists():
            return

        product = self.find_product(self.selected_product_id)
        meter = self.stock_meter
        meter.delete("all")
        width = max(meter.winfo_width(), 100)

        if product is None:
            self.inspect_pill.configure(text="No product selected", fg=COLORS["faint"], bg=COLORS["card"])
            self.ins_name.configure(text="Click a product in the table")
            self.ins_id.configure(text="Its details and stock level will show here.")
            for label in self.ins_tiles.values():
                label.configure(text="--", fg=COLORS["faint"])
            meter.create_rectangle(0, 4, width, 9, outline="", fill=COLORS["card_high"])
            return

        quantity = product["quantity"]
        if quantity == 0:
            status, key = "Out of stock", "red"
        elif quantity < database.LOW_STOCK_THRESHOLD:
            status, key = "Low stock", "amber"
        else:
            status, key = "In stock", "green"
        color = COLORS[key]

        self.inspect_pill.configure(text=status, fg=color, bg=COLORS[f"{key}_soft"])
        name = product["product_name"]
        self.ins_name.configure(text=name if len(name) <= 34 else name[:33] + "…")
        who = product.get("updated_by_name")
        changed = f"  ·  Last change by @{who}, {nice_time(product.get('updated_at'))}" if who else ""
        self.ins_id.configure(text=f"P{product['product_id']:03d}  ·  {product['category']}{changed}")
        self.ins_tiles["Stock"].configure(text=f"{quantity:,} pcs", fg=color)
        self.ins_tiles["Unit Price"].configure(text=peso(product["unit_price"]), fg=COLORS["text"])
        self.ins_tiles["Total Value"].configure(text=peso(product["total"]), fg=COLORS["text"])
        self.ins_tiles["Status"].configure(text={"red": "Empty", "amber": "Low", "green": "OK"}[key], fg=color)

        # Stock meter: this product's stock compared with the biggest stock in the list.
        biggest = max(max(p["quantity"] for p in self.products), database.LOW_STOCK_THRESHOLD * 2)
        meter.create_rectangle(0, 4, width, 9, outline="", fill=COLORS["card_high"])
        meter.create_rectangle(0, 4, max(int(width * quantity / biggest), 3), 9, outline="", fill=color)
        threshold_x = int(width * database.LOW_STOCK_THRESHOLD / biggest)
        meter.create_line(threshold_x, 0, threshold_x, 13, fill=COLORS["red"], dash=(2, 2))

    def start_new_product(self):
        """Open the inventory form in add mode from any page."""
        self.show_page("inventory")
        self.clear_fields()
        self.root.after_idle(self.name_entry.focus_set)

    def focus_product_search(self):
        """Open Inventory and focus Search, including when invoked from a dashboard."""
        self.show_page("inventory")
        self.root.after_idle(self.search_entry.focus_set)

    def clear_product_form(self):
        """Make the global Esc/Clear shortcut visible and useful from every page."""
        self.show_page("inventory")
        self.clear_fields()

    def set_category_filter(self, category):
        self.category_filter = category
        self.render_table()

    def sign_out(self):
        if not messagebox.askyesno("Sign Out", "Do you want to sign out?", parent=self.root):
            return
        try:
            auth.sign_out(self.user)
        except sqlite3.DatabaseError:
            pass
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
            self.toast_job = None
        for sequence in ("<Escape>", "<Control-f>", "<Control-F>", "<Control-l>", "<Control-L>"):
            self.root.unbind(sequence)
        if self.viewer_is_open():
            self.viewer.root.destroy()
        self.viewer = None
        for widget in self.root.winfo_children():
            widget.destroy()
        if self.on_sign_out:
            self.on_sign_out()

    def toggle_theme(self):
        """Switch between dark and light mode by rebuilding the screen with the new colors."""
        new_mode = "light" if theme.MODE == "dark" else "dark"
        theme.set_mode(new_mode)
        self.rebuild_screen()
        self.log("THEME", f"Switched to {new_mode} mode.")

    def rebuild_screen(self):
        """Draw the whole window again (after a theme or name change), keeping what was typed."""
        page, page_user_id = self.page, self.page_user_id
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
            self.toast_job = None
        if self.placeholder_trace:
            self.search_var.trace_remove("write", self.placeholder_trace)
            self.placeholder_trace = None
        for variable, trace in self.form_traces:
            variable.trace_remove("write", trace)
        self.form_traces = []
        viewer_was_open = self.viewer_is_open()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.viewer = None

        # The typed form values, search text, and log are kept because they live outside the widgets.
        theme.apply_ttk_theme(self.root)
        self.build_interface()
        self.refresh_data()
        self.set_edit_mode(self.selected_product_id is not None)
        if page != "inventory":
            self.show_page(page, page_user_id)
        if viewer_was_open:
            self.open_database_viewer()

    def viewer_is_open(self):
        return self.viewer is not None and self.viewer.root.winfo_exists()

    def open_database_viewer(self):
        """Open the DB Records window, or bring it to the front if it is already open (admins only)."""
        import database_viewer

        try:
            auth.require_permission(self.user, "view_database")
        except ValidationError as error:
            self.show_toast(error.message, "error")
            return

        if self.viewer_is_open():
            self.viewer.load_records()
            self.viewer.root.deiconify()
            self.viewer.root.lift()
            return

        window = tk.Toplevel(self.root)
        self.viewer = database_viewer.DatabaseViewer(window)

    # ------------------------------------------------------------------- CRUD

    def validate_inputs(self):
        """Check the form. Shows a red message and returns None if something is wrong."""
        self.error_var.set("")
        try:
            return validate_product(
                self.product_name_var.get(), self.category_var.get(), self.quantity_var.get(), self.unit_price_var.get()
            )
        except ValidationError as error:
            fields = {"name": self.name_entry, "category": self.category_entry, "quantity": self.quantity_entry, "price": self.price_entry}
            self.show_error(error.message, fields.get(error.field))
            return None

    def database_problem(self, action):
        self.log("ERROR", f"Could not {action}. The database may be open in another program.")
        messagebox.showerror(
            "Database Problem",
            f"Could not {action}.\n\nThe database file may be locked by another program. Close it and try again.",
            parent=self.root,
        )

    def save_from_keyboard(self):
        if self.selected_product_id is None:
            self.add_product()
        else:
            self.update_product()

    def add_product(self):
        try:
            auth.require_permission(self.user, "edit_products")
        except ValidationError as error:
            self.show_error(error.message)
            return
        values = self.validate_inputs()
        if values is None:
            return

        try:
            result = database.add_product(*values, user_id=self.user.user_id)
        except sqlite3.DatabaseError:
            self.database_problem("save the product")
            return

        if result == "too_much":
            self.show_error(
                f"Adding {values[2]:,} pcs would put this product over {database.MAX_QUANTITY:,} pcs.", self.quantity_entry
            )
            return
        if result == "forbidden":
            self.show_error("Your account no longer has permission to change products.")
            return

        self.refresh_data()
        self.clear_fields()
        name, category, quantity, unit_price = values
        if result == "restocked":
            self.log("RESTOCK", f"{name} already exists, so {quantity:,} pcs were added to its stock.", save=True)
            self.show_toast("Same product already exists, so its quantity was increased.", "info")
        else:
            self.log("ADD", f"Added {name} ({category}), {quantity:,} pcs @ {peso(unit_price)}.", save=True)
            self.show_toast("Product added successfully.")

    def update_product(self):
        try:
            auth.require_permission(self.user, "edit_products")
        except ValidationError as error:
            self.show_error(error.message)
            return
        if self.selected_product_id is None:
            self.show_error("Please select a product to update.")
            return

        values = self.validate_inputs()
        if values is None:
            return

        product_id = self.selected_product_id
        try:
            result = database.update_product(product_id, *values, user_id=self.user.user_id)
        except sqlite3.DatabaseError:
            self.database_problem("update the product")
            return

        if result == "duplicate":
            self.show_error("Another product already has the same name, category, and price.", self.name_entry)
            return
        if result == "forbidden":
            self.show_error("Your account no longer has permission to change products.")
            return
        if result == "missing":
            self.refresh_data()
            self.clear_fields()
            self.show_toast("That product no longer exists. The list was refreshed.", "error")
            return

        self.refresh_data()
        self.clear_fields()
        self.log("UPDATE", f"P{product_id:03d} {values[0]} updated: {values[2]:,} pcs @ {peso(values[3])}.", save=True)
        self.show_toast("Product updated successfully.")

    def delete_product(self):
        try:
            auth.require_permission(self.user, "delete_products")
        except ValidationError as error:
            self.show_error(error.message)
            return
        if self.selected_product_id is None:
            self.show_error("Please select a product to delete.")
            return

        product_id = self.selected_product_id
        product = self.find_product(product_id)
        name = product["product_name"] if product else self.product_name_var.get()
        confirmed = messagebox.askyesno(
            "Delete Product",
            f"Are you sure you want to delete \"{name}\"?\n\nThis cannot be undone.",
            icon=messagebox.WARNING,
            parent=self.root,
        )
        if not confirmed:
            return

        try:
            deleted = database.delete_product(product_id, user_id=self.user.user_id)
        except sqlite3.DatabaseError:
            self.database_problem("delete the product")
            return

        self.refresh_data()
        self.clear_fields()
        if deleted == "forbidden":
            self.show_error("Only an active administrator can delete products.")
            return
        if deleted == "missing":
            self.show_toast("That product was already deleted. The list was refreshed.", "error")
            return
        self.log("DELETE", f"P{product_id:03d} {name} was deleted.", save=True)
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
        self.out_stock_unit_var.set("add stock" if out else "")

        count = len(self.products)
        in_stock = count - len(low)
        self.health_ratio = in_stock / count if count else 0.0
        self.health_var.set(f"{self.health_ratio:.0%}")
        self.draw_health()
        self.sidebar_records_var.set(f"{count} record{'s' if count != 1 else ''}")
        self.footer_var.set(
            f"Records: {count:,}   ·   Units in stock: {totals['total_stock_units']:,}   ·   Signed in at {self.started_at}"
        )
        try:
            size = database.DB_PATH.stat().st_size
        except OSError:
            size = 0
        self.db_size_var.set(f"{size / 1024:,.1f} KB")
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
                status, status_tag = "Out of stock", "out"
            elif quantity < database.LOW_STOCK_THRESHOLD:
                status, status_tag = "Low stock", "low"
            else:
                status, status_tag = "In stock", None

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
        self.row_count_var.set(f"{len(products)} of {len(self.products)} shown")
        self.index_var.set(
            f"Sorted by {TABLE_COLUMNS_BY_KEY.get(self.sort_key, 'ID')} ({'high to low' if self.sort_reverse else 'low to high'})"
        )

        if products:
            self.empty_label.place_forget()
        else:
            if self.products:
                self.empty_label.configure(text="No products match your search or filter.\nTry another word or click All.")
            else:
                self.empty_label.configure(text="No products yet.\nAdd your first product using the form on the right.")
            self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)


def setup_window(root):
    root.title(WINDOW_TITLE)
    root.geometry("1280x720")
    root.minsize(1100, 660)
    try:
        root.state("zoomed")  # open maximized on Windows
    except tk.TclError:
        pass
    theme.load_fonts(root)
    theme.apply_ttk_theme(root)


def install_error_handler(root):
    """Show a friendly message instead of a silent crash if something unexpected goes wrong."""

    def report(exc_type, exc_value, exc_traceback):
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        if issubclass(exc_type, sqlite3.DatabaseError):
            text = "The database could not be read or saved. Close any other program using inventory.db and try again."
        else:
            text = "Something went wrong, but your saved products are safe. Please try that again."
        messagebox.showerror("Unexpected Problem", text, parent=root)

    root.report_callback_exception = report


def main():
    root = tk.Tk()
    setup_window(root)
    install_error_handler(root)

    try:
        database.initialize_database()
    except sqlite3.DatabaseError as error:
        traceback.print_exception(type(error), error, error.__traceback__)
        messagebox.showerror("Database Problem", "inventory.db could not be opened. Check file access and try again.", parent=root)
        root.destroy()
        return

    def show_sign_in():
        AuthScreen(root, on_success=show_inventory, mode="staff_sign_in" if database.count_users() else "sign_up")

    def show_inventory(user):
        app = InventoryApp(root, user, on_sign_out=show_sign_in)
        if user.must_change_password:
            app.show_page("profile", user.user_id)
            root.after(
                100,
                lambda: messagebox.showwarning(
                    "Change Temporary Password",
                    "For your security, change the temporary password now in My Dashboard.",
                    parent=root,
                ),
            )
        elif user.is_admin:
            app.show_page("admin")
        app.show_toast(f"Signed in as {user.full_name}.", "info")

    show_sign_in()
    root.mainloop()


if __name__ == "__main__":
    main()
