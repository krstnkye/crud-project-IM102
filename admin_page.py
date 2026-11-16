"""The Admin Dashboard page, shown inside the main window (admins only)."""

import sqlite3
import tkinter as tk
from datetime import datetime, timedelta

import database
from profile_page import ACTION_COLORS, card_header, caps, nice_time, panel, sans, short_time, stat_tiles, table
from theme import COLORS, FlatButton


class AdminPage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS["page"], padx=20, pady=14)
        self.only_products = False
        self.stat_vars = {name: tk.StringVar(value="0") for name in ("members", "active", "today", "week")}
        self.members_note = tk.StringVar()
        self.build()
        self.load()

    def build(self):
        stat_tiles(self.frame, (
            ("members", "Team Members", "strong"),
            ("active", "Active Accounts", "green"),
            ("today", "Product Changes Today", "primary"),
            ("week", "Product Changes, Last 7 Days", "secondary"),
        ), self.stat_vars)
        tk.Label(self.frame, textvariable=self.members_note, bg=COLORS["page"], fg=COLORS["muted"], font=sans(8)).pack(anchor=tk.W, pady=(4, 0))

        # Team list with an Open Profile button.
        outer, card = panel(self.frame, padx=0, pady=0)
        outer.pack(fill=tk.X, pady=(8, 0))
        top = card_header(card, "Team", None)
        FlatButton(
            top, "Open Profile", self.open_selected, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=4, border=COLORS["button"],
        ).pack(side=tk.RIGHT)
        caps(top, "Double-click a person to open their profile and manage the account", weight="normal").pack(side=tk.RIGHT, padx=(0, 12))
        self.team = table(card, (
            ("user", "User", 130, tk.W),
            ("name", "Full Name", 170, tk.W),
            ("role", "Role", 80, tk.W),
            ("status", "Status", 90, tk.W),
            ("changes", "Product Changes", 120, tk.E),
            ("last_change", "Last Change", 150, tk.W),
            ("last_login", "Last Sign-in", 150, tk.W),
        ), height=4)
        self.team.bind("<Double-1>", lambda event: self.open_selected())
        self.team.bind("<Return>", lambda event: self.open_selected())

        # Everyone's activity.
        outer, card = panel(self.frame, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        top = card_header(card, "All Activity")
        self.filter_buttons = {}
        for only, text in ((False, "Everything"), (True, "Product changes only")):
            button = FlatButton(
                top, text, lambda value=only: self.set_filter(value), COLORS["card_high"], COLORS["dim"], COLORS["card_top"],
                font_size=8, padx=9, pady=3, border=COLORS["line"], hover_fg=COLORS["strong"], weight="normal",
            )
            button.pack(side=tk.LEFT, padx=(10, 0))
            self.filter_buttons[only] = button
        caps(top, "Who did what, newest first", weight="normal").pack(side=tk.RIGHT)
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

    def load(self):
        try:
            team = database.get_team_summary()
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
            f"  ·  {len(team) - active} account{'s' if len(team) - active != 1 else ''} turned off"
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
                    "Active" if member["is_active"] else "Turned off",
                    f"{member['changes']:,}",
                    short_time(member["last_change"], "None yet"),
                    short_time(member["last_login"]),
                ),
                tags=tuple(tags),
            )

        self.activity.delete(*self.activity.get_children())
        for index, entry in enumerate(activity):
            self.activity.insert(
                "", tk.END,
                values=(nice_time(entry["created_at"]), f"@{entry['username']}" if entry["username"] else "(deleted user)",
                        entry["action"], entry["details"]),
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
