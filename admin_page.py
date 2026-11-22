"""The Admin Dashboard page, shown inside the main window (admins only)."""

import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

import auth
import database
from profile_page import ACTION_COLORS, card_header, caps, nice_time, panel, sans, short_time, stat_tiles, table
from theme import COLORS, FlatButton
from validation import MIN_PASSWORD_LENGTH, ValidationError


class CreateAccountDialog:
    """Admin-only form for creating Staff or Admin accounts."""

    def __init__(self, parent, admin, on_created):
        self.admin = admin
        self.on_created = on_created
        self.entries = {}
        self.role_var = tk.StringVar(value="Staff")
        self.error_var = tk.StringVar()
        self.show_password = tk.BooleanVar(value=False)

        self.window = tk.Toplevel(parent)
        self.window.title("Create Account")
        self.window.configure(bg=COLORS["page"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        outer = tk.Frame(self.window, bg=COLORS["line"])
        outer.pack(padx=18, pady=18)
        card = tk.Frame(outer, bg=COLORS["card"], padx=26, pady=22, width=430)
        card.pack(padx=1, pady=1)

        tk.Label(card, text="Create user account", bg=COLORS["card"], fg=COLORS["strong"], font=sans(17, "bold")).pack(anchor=tk.W)
        tk.Label(
            card, text="Choose the account role, then give the user their username and password.",
            bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), wraplength=360, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(3, 12))

        self.add_field(card, "full_name", "Full Name")
        self.add_field(card, "username", "Username", "3-20 letters, numbers, . or _")

        role_row = tk.Frame(card, bg=COLORS["card"])
        role_row.pack(fill=tk.X, pady=(12, 0))
        tk.Label(role_row, text="Role", bg=COLORS["card"], fg=COLORS["dim"], font=sans(8, "bold")).pack(anchor=tk.W)
        self.role = ttk.Combobox(role_row, textvariable=self.role_var, values=("Staff", "Admin"), state="readonly", width=36)
        self.role.pack(fill=tk.X, pady=(4, 0))

        self.add_field(card, "password", "Password", f"{MIN_PASSWORD_LENGTH}+ characters, with a letter and number", secret=True)
        self.add_field(card, "confirm", "Confirm Password", secret=True)

        show = tk.Checkbutton(
            card, text="Show passwords", variable=self.show_password, command=self.update_password_visibility,
            bg=COLORS["card"], fg=COLORS["dim"], activebackground=COLORS["card"], activeforeground=COLORS["strong"],
            selectcolor=COLORS["input"], font=sans(9), bd=0, highlightthickness=0,
        )
        show.pack(anchor=tk.W, pady=(10, 0))

        self.error = tk.Label(
            card, textvariable=self.error_var, bg=COLORS["red_soft"], fg=COLORS["red"], font=sans(9, "bold"),
            wraplength=360, justify=tk.LEFT, anchor=tk.W, padx=10, pady=7,
        )

        buttons = tk.Frame(card, bg=COLORS["card"])
        buttons.pack(fill=tk.X, pady=(18, 0))
        FlatButton(
            buttons, "Cancel", self.close, COLORS["card_high"], COLORS["dim"], COLORS["card_top"],
            font_size=9, pady=8, border=COLORS["line_high"], hover_fg=COLORS["strong"],
        ).pack(side=tk.LEFT)
        self.create_button = FlatButton(
            buttons, "Create Account", self.submit, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=9, pady=8, border=COLORS["button"],
        )
        self.create_button.pack(side=tk.RIGHT)

        self.window.bind("<Return>", lambda event: self.submit())
        self.window.bind("<Escape>", lambda event: self.close())
        self.window.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.window.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.window.winfo_reqheight()) // 2
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.window.grab_set()
        self.entries["full_name"].focus_set()

    def add_field(self, parent, name, label, hint=None, secret=False):
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill=tk.X, pady=(12, 0))
        heading = tk.Frame(row, bg=COLORS["card"])
        heading.pack(fill=tk.X)
        tk.Label(heading, text=label, bg=COLORS["card"], fg=COLORS["dim"], font=sans(8, "bold")).pack(side=tk.LEFT)
        if hint:
            tk.Label(heading, text=hint, bg=COLORS["card"], fg=COLORS["faint"], font=sans(8)).pack(side=tk.RIGHT)
        entry = tk.Entry(
            row, bg=COLORS["input"], fg=COLORS["text"], insertbackground=COLORS["primary"],
            selectbackground=COLORS["primary"], selectforeground=COLORS["button_text"], relief=tk.FLAT,
            highlightthickness=1, highlightbackground=COLORS["line_high"], highlightcolor=COLORS["primary"],
            font=sans(10), show="*" if secret else "",
        )
        entry.pack(fill=tk.X, ipady=7, pady=(4, 0))
        entry.secret = secret
        self.entries[name] = entry

    def update_password_visibility(self):
        for entry in self.entries.values():
            if entry.secret:
                entry.configure(show="" if self.show_password.get() else "*")

    def submit(self):
        self.create_button.set_enabled(False)
        values = {name: entry.get() for name, entry in self.entries.items()}
        try:
            user = auth.admin_create_user(
                self.admin, values["full_name"], values["username"], values["password"], values["confirm"],
                self.role_var.get().lower(),
            )
        except ValidationError as error:
            self.create_button.set_enabled(True)
            self.error_var.set(error.message)
            self.error.pack(fill=tk.X, pady=(12, 0), before=self.error.master.winfo_children()[-1])
            target = self.role if error.field == "role" else self.entries.get(error.field)
            if target is not None:
                target.focus_set()
            return
        self.close()
        self.on_created(user)

    def close(self):
        if self.window.winfo_exists():
            self.window.grab_release()
            self.window.destroy()


class AdminPage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS["page"])
        self.canvas = tk.Canvas(self.frame, bg=COLORS["page"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.content = tk.Frame(self.canvas, bg=COLORS["page"], padx=20, pady=14)
        self.content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_content_width)
        self.canvas.bind("<MouseWheel>", self._scroll)
        self.content.bind("<MouseWheel>", self._scroll)
        self.only_products = False
        self.stat_vars = {name: tk.StringVar(value="0") for name in ("members", "active", "today", "week")}
        self.members_note = tk.StringVar()
        self.build()
        self.load()

    def _sync_scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_content_width(self, event):
        self.canvas.itemconfigure(self.content_window, width=event.width)

    def _scroll(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def build(self):
        stat_tiles(self.content, (
            ("members", "Total Users", "strong"),
            ("active", "Active Users", "green"),
            ("today", "Changes Today", "primary"),
            ("week", "Changes in the Last 7 Days", "secondary"),
        ), self.stat_vars)
        tk.Label(self.content, textvariable=self.members_note, bg=COLORS["page"], fg=COLORS["muted"], font=sans(8)).pack(anchor=tk.W, pady=(4, 0))

        # Requests have no login access until an administrator approves one here.
        outer, card = panel(self.content, padx=0, pady=0)
        outer.pack(fill=tk.X, pady=(8, 0))
        top = card_header(card, "Pending Account Requests", None)
        FlatButton(
            top, "Reject", self.reject_selected, COLORS["red_soft"], COLORS["red"], COLORS["red_hover"],
            font_size=8, pady=4, border=COLORS["red_line"],
        ).pack(side=tk.RIGHT)
        FlatButton(
            top, "Approve as Admin", lambda: self.approve_selected("admin"), COLORS["card_high"], COLORS["strong"], COLORS["card_top"],
            font_size=8, pady=4, border=COLORS["line_high"], hover_fg=COLORS["primary"],
        ).pack(side=tk.RIGHT, padx=(0, 8))
        FlatButton(
            top, "Approve as Staff", lambda: self.approve_selected("staff"), COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=4, border=COLORS["button"],
        ).pack(side=tk.RIGHT, padx=(0, 8))
        self.requests = table(card, (
            ("user", "Username", 160, tk.W),
            ("name", "Full Name", 240, tk.W),
            ("role", "Requested Role", 150, tk.W),
            ("requested", "Requested", 190, tk.W),
        ), height=2)

        # User list with a View Profile button.
        outer, card = panel(self.content, padx=0, pady=0)
        outer.pack(fill=tk.X, pady=(8, 0))
        top = card_header(card, "Users", None)
        FlatButton(
            top, "Create Account", self.create_account, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=4, border=COLORS["button"],
        ).pack(side=tk.RIGHT)
        FlatButton(
            top, "View Profile", self.open_selected, COLORS["card_high"], COLORS["text"], COLORS["card_top"],
            font_size=8, pady=4, border=COLORS["line_high"], hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT, padx=(0, 8))
        caps(top, "Double-click a user to view their profile", weight="normal").pack(side=tk.RIGHT, padx=(0, 12))
        self.team = table(card, (
            ("user", "User", 130, tk.W),
            ("name", "Full Name", 170, tk.W),
            ("role", "Role", 80, tk.W),
            ("status", "Status", 90, tk.W),
            ("changes", "Changes", 120, tk.E),
            ("last_change", "Last Update", 150, tk.W),
            ("last_login", "Last Sign In", 150, tk.W),
        ), height=4)
        self.team.bind("<Double-1>", lambda event: self.open_selected())
        self.team.bind("<Return>", lambda event: self.open_selected())

        # Everyone's activity.
        outer, card = panel(self.content, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        top = card_header(card, "All Activity")
        self.filter_buttons = {}
        for only, text in ((False, "All"), (True, "Products Only")):
            button = FlatButton(
                top, text, lambda value=only: self.set_filter(value), COLORS["card_high"], COLORS["dim"], COLORS["card_top"],
                font_size=8, padx=9, pady=3, border=COLORS["line"], hover_fg=COLORS["strong"], weight="normal",
            )
            button.pack(side=tk.LEFT, padx=(10, 0))
            self.filter_buttons[only] = button
        caps(top, "Newest first", weight="normal").pack(side=tk.RIGHT)
        self.activity = table(card, (
            ("time", "When", 165, tk.W),
            ("user", "User", 120, tk.W),
            ("action", "Action", 90, tk.W),
            ("details", "Details", 470, tk.W),
        ), height=6)

    def set_filter(self, only_products):
        self.only_products = only_products
        self.load()

    def open_selected(self):
        selected = self.team.selection()
        if selected:
            self.app.show_page("profile", int(selected[0]))

    def create_account(self):
        CreateAccountDialog(self.app.root, self.app.user, self.account_created)

    def account_created(self, user):
        self.load()
        self.app.show_toast(f"{user.role_name} account @{user.username} was created.")

    def selected_request_id(self):
        selected = self.requests.selection()
        if not selected:
            self.app.show_toast("Select an account request first.", "error")
            return None
        return int(selected[0])

    def approve_selected(self, role):
        request_id = self.selected_request_id()
        if request_id is None:
            return
        if role == "admin" and not messagebox.askyesno(
            "Approve Administrator",
            "Approve this request as an administrator?\n\nAdministrators can manage accounts and access all system features.",
            parent=self.app.root,
        ):
            return
        try:
            user = auth.admin_approve_registration(self.app.user, request_id, role)
        except ValidationError as error:
            self.app.show_toast(error.message, "error")
            self.load()
            return
        self.load()
        self.app.show_toast(f"Approved @{user.username} as {user.role_name}.")

    def reject_selected(self):
        request_id = self.selected_request_id()
        if request_id is None:
            return
        if not messagebox.askyesno(
            "Reject Account Request", "Reject the selected account request?", parent=self.app.root
        ):
            return
        try:
            username, _ = auth.admin_reject_registration(self.app.user, request_id)
        except ValidationError as error:
            self.app.show_toast(error.message, "error")
            self.load()
            return
        self.load()
        self.app.show_toast(f"Rejected the request from @{username}.", "info")

    def load(self):
        try:
            team = database.get_team_summary()
            requests = database.get_pending_registration_requests()
            activity = database.get_all_activity(300, self.only_products)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            changes_today = database.count_changes_since(today.isoformat(sep=" "))
            changes_week = database.count_changes_since((today - timedelta(days=6)).isoformat(sep=" "))
        except sqlite3.DatabaseError:
            self.app.database_problem("load the Admin Dashboard")
            return

        admins = sum(1 for m in team if m["role"] == "admin")
        active = sum(1 for m in team if m["is_active"])
        self.stat_vars["members"].set(f"{len(team)}")
        self.stat_vars["active"].set(f"{active}")
        self.stat_vars["today"].set(f"{changes_today:,}")
        self.stat_vars["week"].set(f"{changes_week:,}")
        self.members_note.set(
            f"{admins} admin{'s' if admins != 1 else ''} and {len(team) - admins} staff"
            f"  ·  {len(team) - active} inactive  ·  {len(requests)} pending request{'s' if len(requests) != 1 else ''}"
        )

        self.requests.delete(*self.requests.get_children())
        for index, request in enumerate(requests):
            self.requests.insert(
                "", tk.END, iid=str(request["request_id"]),
                values=(
                    f"@{request['username']}", request["full_name"], request["requested_role"].title(),
                    nice_time(request["created_at"]),
                ),
                tags=("even" if index % 2 == 0 else "odd",),
            )

        self.team.delete(*self.team.get_children())
        for index, member in enumerate(team):
            is_me = member["user_id"] == self.app.user.user_id
            tags = ["even" if index % 2 == 0 else "odd"]
            if not member["is_active"]:
                tags.append("off")
            elif is_me:
                tags.append("me")
            self.team.insert(
                "", tk.END, iid=str(member["user_id"]),
                values=(
                    f"@{member['username']}" + ("  (you)" if is_me else ""),
                    member["full_name"],
                    "Admin" if member["role"] == "admin" else "Staff",
                    "Active" if member["is_active"] else "Inactive",
                    f"{member['changes']:,}",
                    short_time(member["last_change"], "None"),
                    short_time(member["last_login"]),
                ),
                tags=tuple(tags),
            )

        self.activity.delete(*self.activity.get_children())
        for index, entry in enumerate(activity):
            self.activity.insert(
                "", tk.END,
                values=(nice_time(entry["created_at"]), f"@{entry['username']}" if entry["username"] else "(deleted user)",
                        database.action_label(entry["action"]), entry["details"]),
                tags=("even" if index % 2 == 0 else "odd", ACTION_COLORS.get(entry["action"], "plain")),
            )

        for only, button in self.filter_buttons.items():
            active_filter = only == self.only_products
            button.colors = (
                COLORS["primary_soft"] if active_filter else COLORS["card_high"],
                COLORS["primary"] if active_filter else COLORS["dim"],
                COLORS["card_top"], COLORS["strong"],
            )
            button.configure(bg=button.colors[0], fg=button.colors[1])
