"""The My Profile page: who the signed-in user is, what they changed, and the whole team's activity."""

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import auth
import database
import theme
from theme import COLORS, FlatButton
from validation import ValidationError


def sans(size, weight="normal"):
    return (theme.FONT, size, weight)


def nice_time(text, empty="Never"):
    """2026-11-16 14:05:09 -> Nov 16, 2026 2:05 PM"""
    if not text:
        return empty
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    return moment.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")


def short_time(text, empty="Never"):
    """2026-11-16 14:05:09 -> Nov 16 2:05 PM (for narrow columns)"""
    if not text:
        return empty
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    return moment.strftime("%b %d %I:%M %p").replace(" 0", " ")


# Only deletes and account changes are colored, so they stand out in the history.
ACTION_COLORS = {"DELETE": "red", "PROFILE": "amber", "PASSWORD": "amber", "SIGN IN": "muted", "SIGN UP": "muted", "SIGN OUT": "muted"}


class ProfilePage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS["page"], padx=20, pady=14)
        self.name_var = tk.StringVar(value=app.user.full_name)
        self.password_vars = {name: tk.StringVar() for name in ("current", "new", "confirm")}
        self.name_message = tk.StringVar()
        self.password_message = tk.StringVar()
        self.stat_vars = {name: tk.StringVar(value="0") for name in ("total", "ADD", "UPDATE", "DELETE")}
        self.build()
        self.load()

    @property
    def user(self):
        return self.app.user

    # ------------------------------------------------------------------ layout

    def panel(self, parent, padx=16, pady=14):
        outer = tk.Frame(parent, bg=COLORS["line"])
        inner = tk.Frame(outer, bg=COLORS["card"], padx=padx, pady=pady)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return outer, inner

    def caps(self, parent, text, color=None, size=8, weight="bold"):
        return tk.Label(parent, text=text, bg=COLORS["card"], fg=color or COLORS["muted"], font=sans(size, weight))

    def build(self):
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)

        left = tk.Frame(self.frame, bg=COLORS["page"], width=330)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        left.pack_propagate(False)
        right = tk.Frame(self.frame, bg=COLORS["page"])
        right.grid(row=0, column=1, sticky="nsew")

        self.build_identity(left)
        self.build_settings(left)
        self.build_stats(right)
        self.build_team(right)
        self.build_history(right)

    def build_identity(self, parent):
        outer, card = self.panel(parent)
        outer.pack(fill=tk.X)
        row = tk.Frame(card, bg=COLORS["card"])
        row.pack(fill=tk.X)
        self.avatar = tk.Canvas(row, width=58, height=58, bg=COLORS["card"], highlightthickness=0)
        self.avatar.pack(side=tk.LEFT)
        names = tk.Frame(row, bg=COLORS["card"])
        names.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)
        self.full_name_label = tk.Label(names, bg=COLORS["card"], fg=COLORS["strong"], font=sans(14, "bold"), anchor=tk.W)
        self.full_name_label.pack(fill=tk.X)
        tk.Label(names, text=f"@{self.user.username}", bg=COLORS["card"], fg=COLORS["primary"], font=sans(9, "bold"), anchor=tk.W).pack(fill=tk.X)

        facts = tk.Frame(card, bg=COLORS["card"])
        facts.pack(fill=tk.X, pady=(12, 0))
        self.fact_labels = {}
        for name in ("User ID", "Member since", "Previous sign-in", "Last product change"):
            line = tk.Frame(facts, bg=COLORS["card"])
            line.pack(fill=tk.X, pady=1)
            tk.Label(line, text=name, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT)
            value = tk.Label(line, bg=COLORS["card"], fg=COLORS["text"], font=sans(8, "bold"))
            value.pack(side=tk.RIGHT)
            self.fact_labels[name] = value

    def build_settings(self, parent):
        outer, card = self.panel(parent)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.caps(card, "Edit Profile", color=COLORS["primary"], size=9).pack(anchor=tk.W)
        self.name_entry = self.field(card, "Full Name", self.name_var)
        self.name_note = self.message_label(card, self.name_message)
        FlatButton(
            card, "Save Name", self.save_name, COLORS["card_high"], COLORS["strong"], COLORS["card_top"],
            font_size=8, pady=6, border=COLORS["line_high"],
        ).pack(fill=tk.X, pady=(8, 0))

        tk.Frame(card, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=12)
        self.caps(card, "Change Password", color=COLORS["primary"], size=9).pack(anchor=tk.W)
        self.password_entries = {
            "current": self.field(card, "Current Password", self.password_vars["current"], secret=True),
            "new": self.field(card, "New Password", self.password_vars["new"], secret=True, hint="8+ chars, a letter and a number"),
            "confirm": self.field(card, "Confirm New Password", self.password_vars["confirm"], secret=True),
        }
        self.password_note = self.message_label(card, self.password_message)
        FlatButton(
            card, "Change Password", self.save_password, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=7, border=COLORS["button"],
        ).pack(fill=tk.X, pady=(8, 0))

    def field(self, parent, label, variable, secret=False, hint=None):
        top = tk.Frame(parent, bg=COLORS["card"])
        top.pack(fill=tk.X, pady=(8, 0))
        tk.Label(top, text=label, bg=COLORS["card"], fg=COLORS["dim"], font=sans(8, "bold")).pack(side=tk.LEFT)
        if hint:
            tk.Label(top, text=hint, bg=COLORS["card"], fg=COLORS["faint"], font=sans(7)).pack(side=tk.RIGHT)
        box = tk.Frame(parent, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line_high"])
        box.pack(fill=tk.X, pady=(3, 0))
        entry = tk.Entry(
            box, textvariable=variable, bg=COLORS["input"], fg=COLORS["text"], insertbackground=COLORS["primary"],
            relief=tk.FLAT, bd=0, highlightthickness=0, font=sans(9), show="•" if secret else "",
        )
        entry.pack(fill=tk.X, ipady=4, padx=8)
        entry.bind("<FocusIn>", lambda e: box.configure(highlightbackground=COLORS["primary"]), add="+")
        entry.bind("<FocusOut>", lambda e: box.configure(highlightbackground=COLORS["line_high"]), add="+")
        return entry

    def message_label(self, parent, variable):
        anchor = tk.Frame(parent, bg=COLORS["card"])
        anchor.pack(fill=tk.X)
        label = tk.Label(anchor, textvariable=variable, font=sans(8, "bold"), wraplength=280, justify=tk.LEFT, anchor=tk.W, padx=8, pady=4)
        label.anchor_frame = anchor
        return label

    def set_message(self, label, variable, text, kind):
        variable.set(text)
        if not text:
            label.pack_forget()
            return
        if kind == "success":
            label.configure(bg=COLORS["green_soft"], fg=COLORS["green"])
        else:
            label.configure(bg=COLORS["red_soft"], fg=COLORS["red"])
        label.pack(fill=tk.X, pady=(6, 0))

    def build_stats(self, parent):
        strip = tk.Frame(parent, bg=COLORS["page"])
        strip.pack(fill=tk.X)
        tiles = (
            ("total", "My Product Changes", "strong"),
            ("ADD", "Products Added", "green"),
            ("UPDATE", "Updates and Restocks", "primary"),
            ("DELETE", "Products Deleted", "red"),
        )
        for index, (key, label, color) in enumerate(tiles):
            strip.columnconfigure(index, weight=1, uniform="stats")
            outer, card = self.panel(strip, padx=14, pady=10)
            outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            self.caps(card, label).pack(anchor=tk.W)
            tk.Label(card, textvariable=self.stat_vars[key], bg=COLORS["card"], fg=COLORS[color], font=sans(17, "bold")).pack(anchor=tk.W)

    def table(self, parent, columns, height):
        area = tk.Frame(parent, bg=COLORS["card"])
        area.pack(fill=tk.BOTH, expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        tree = ttk.Treeview(area, columns=[c[0] for c in columns], show="headings", selectmode="browse", height=height)
        for key, heading, width, anchor in columns:
            tree.heading(key, text=heading, anchor=anchor)
            tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
        scrollbar = ttk.Scrollbar(area, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.tag_configure("even", background=COLORS["card"])
        tree.tag_configure("odd", background=COLORS["row_alt"])
        for name in set(ACTION_COLORS.values()):
            tree.tag_configure(name, foreground=COLORS[name])
        tree.tag_configure("plain", foreground=COLORS["text"])
        tree.tag_configure("me", foreground=COLORS["primary"])
        return tree

    def build_history(self, parent):
        outer, card = self.panel(parent, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        top = tk.Frame(card, bg=COLORS["card"], padx=16, pady=9)
        top.pack(fill=tk.X)
        tk.Label(top, text="My Activity", bg=COLORS["card"], fg=COLORS["strong"], font=sans(12, "bold")).pack(side=tk.LEFT)
        self.history_count = tk.Label(top, bg=COLORS["primary_soft"], fg=COLORS["primary"], font=sans(8, "bold"), padx=6, pady=1)
        self.history_count.pack(side=tk.LEFT, padx=(10, 0))
        self.caps(top, "Everything you did, saved in activity_log", weight="normal").pack(side=tk.RIGHT)
        self.history = self.table(card, (
            ("time", "When", 165, tk.W),
            ("action", "Action", 95, tk.W),
            ("details", "Details", 470, tk.W),
        ), height=5)

    def build_team(self, parent):
        outer, card = self.panel(parent, padx=0, pady=0)
        outer.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))
        top = tk.Frame(card, bg=COLORS["card"], padx=16, pady=9)
        top.pack(fill=tk.X)
        tk.Label(top, text="Team", bg=COLORS["card"], fg=COLORS["strong"], font=sans(12, "bold")).pack(side=tk.LEFT)
        self.caps(top, "Who made how many product changes", weight="normal").pack(side=tk.RIGHT)
        self.team = self.table(card, (
            ("user", "User", 120, tk.W),
            ("name", "Full Name", 160, tk.W),
            ("changes", "Product Changes", 120, tk.E),
            ("last_change", "Last Change", 165, tk.W),
            ("last_login", "Last Sign-in", 165, tk.W),
        ), height=3)

    # ---------------------------------------------------------------- data

    def draw_avatar(self):
        canvas = self.avatar
        canvas.delete("all")
        canvas.create_oval(2, 2, 56, 56, fill=COLORS["primary_soft"], outline=COLORS["primary_line"], width=2)
        canvas.create_text(29, 29, text=self.user.initials, fill=COLORS["primary"], font=sans(16, "bold"))

    def load(self):
        user = self.user
        self.draw_avatar()
        self.full_name_label.configure(text=user.full_name if len(user.full_name) <= 24 else user.full_name[:23] + "…")
        try:
            row = database.get_user_by_id(user.user_id)
            stats = database.get_user_stats(user.user_id)
            history = database.get_user_activity(user.user_id, 200)
            team = database.get_team_summary()
        except sqlite3.DatabaseError:
            self.app.database_problem("load the profile")
            return

        self.fact_labels["User ID"].configure(text=f"U{user.user_id:03d}")
        self.fact_labels["Member since"].configure(text=nice_time(row["created_at"] if row else None, "--"))
        self.fact_labels["Previous sign-in"].configure(text=nice_time(user.last_login, "First time"))
        self.fact_labels["Last product change"].configure(text=nice_time(stats["last_change"], "None yet"))

        self.stat_vars["total"].set(f"{stats['total']:,}")
        self.stat_vars["ADD"].set(f"{stats['ADD']:,}")
        self.stat_vars["UPDATE"].set(f"{stats['UPDATE'] + stats['RESTOCK']:,}")
        self.stat_vars["DELETE"].set(f"{stats['DELETE']:,}")

        self.history.delete(*self.history.get_children())
        for index, entry in enumerate(history):
            self.history.insert(
                "", tk.END, values=(nice_time(entry["created_at"]), entry["action"], entry["details"]),
                tags=("even" if index % 2 == 0 else "odd", ACTION_COLORS.get(entry["action"], "plain")),
            )
        self.history_count.configure(text=f"{len(history)} saved action{'s' if len(history) != 1 else ''}")

        self.team.delete(*self.team.get_children())
        for index, member in enumerate(team):
            tags = ["even" if index % 2 == 0 else "odd"]
            if member["user_id"] == user.user_id:
                tags.append("me")
            self.team.insert(
                "", tk.END,
                values=(
                    f"@{member['username']}" + ("  (you)" if member["user_id"] == user.user_id else ""),
                    member["full_name"], f"{member['changes']:,}",
                    short_time(member["last_change"], "None yet"), short_time(member["last_login"]),
                ),
                tags=tuple(tags),
            )

    # ---------------------------------------------------------------- actions

    def save_name(self):
        self.set_message(self.name_note, self.name_message, "", "error")
        try:
            self.app.user = auth.change_full_name(self.user, self.name_var.get())
        except ValidationError as error:
            self.set_message(self.name_note, self.name_message, f"⚠  {error.message}", "error")
            self.name_entry.focus_set()
            return
        except sqlite3.DatabaseError:
            self.app.database_problem("save your name")
            return
        self.name_var.set(self.user.full_name)
        self.set_message(self.name_note, self.name_message, "✓  Your name was saved.", "success")
        self.app.on_profile_changed()
        self.load()

    def save_password(self):
        self.set_message(self.password_note, self.password_message, "", "error")
        values = {name: var.get() for name, var in self.password_vars.items()}
        try:
            auth.change_password(self.user, values["current"], values["new"], values["confirm"])
        except ValidationError as error:
            self.set_message(self.password_note, self.password_message, f"⚠  {error.message}", "error")
            entry = self.password_entries.get(error.field)
            if entry is not None:
                entry.focus_set()
                entry.select_range(0, tk.END)
            return
        except sqlite3.DatabaseError:
            self.app.database_problem("change your password")
            return
        for var in self.password_vars.values():
            var.set("")
        self.set_message(self.password_note, self.password_message, "✓  Password changed. Use the new one next time you sign in.", "success")
        self.app.log("PASSWORD", "Password changed.")
        self.load()
