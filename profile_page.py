"""Profile pages, shown inside the main window.

* My Dashboard: the signed-in user's own details, counts, and history, with forms to change
  their name and password. This is the staff dashboard.
* A staff or admin profile opened from the Admin Dashboard: the same details, plus account
  controls for the admin (role, activate/deactivate, reset password).
"""

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

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


def initials(full_name):
    parts = full_name.split()
    letters = (parts[0][0] + parts[-1][0]) if len(parts) > 1 else full_name[:2]
    return letters.upper()


# Only deletes and account changes are colored, so they stand out in a history list.
ACTION_COLORS = {
    "DELETE": "red", "PROFILE": "amber", "PASSWORD": "amber", "ROLE": "amber", "ACCOUNT": "amber",
    "SIGN IN": "muted", "SIGN UP": "muted", "SIGN OUT": "muted",
}


# ---------------------------------------------------------------- shared building blocks


def panel(parent, padx=16, pady=14):
    outer = tk.Frame(parent, bg=COLORS["line"])
    inner = tk.Frame(outer, bg=COLORS["card"], padx=padx, pady=pady)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    return outer, inner


def caps(parent, text, color=None, size=8, weight="bold"):
    return tk.Label(parent, text=text, bg=COLORS["card"], fg=color or COLORS["muted"], font=sans(size, weight))


def stat_tiles(parent, tiles, variables):
    strip = tk.Frame(parent, bg=COLORS["page"])
    strip.pack(fill=tk.X)
    for index, (key, label, color) in enumerate(tiles):
        strip.columnconfigure(index, weight=1, uniform="stats")
        outer, card = panel(strip, padx=14, pady=10)
        outer.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
        caps(card, label).pack(anchor=tk.W)
        tk.Label(card, textvariable=variables[key], bg=COLORS["card"], fg=COLORS[color], font=sans(17, "bold")).pack(anchor=tk.W)
    return strip


def table(parent, columns, height):
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
    tree.tag_configure("off", foreground=COLORS["faint"])
    return tree


def card_header(card, title, note=None):
    top = tk.Frame(card, bg=COLORS["card"], padx=16, pady=9)
    top.pack(fill=tk.X)
    tk.Label(top, text=title, bg=COLORS["card"], fg=COLORS["strong"], font=sans(12, "bold")).pack(side=tk.LEFT)
    if note:
        caps(top, note, weight="normal").pack(side=tk.RIGHT)
    return top


def role_badge(parent, role, active=True, bg=None):
    if not active:
        text, fg, soft = "Inactive", COLORS["faint"], COLORS["card_high"]
    elif role == "admin":
        text, fg, soft = "Admin", COLORS["secondary"], COLORS["secondary_soft"]
    else:
        text, fg, soft = "Staff", COLORS["primary"], COLORS["primary_soft"]
    return tk.Label(parent, text=text, bg=soft, fg=fg, font=sans(8, "bold"), padx=6, pady=1)


# ---------------------------------------------------------------- the page


class ProfilePage:
    def __init__(self, parent, app, user_id=None):
        self.app = app
        self.user_id = user_id or app.user.user_id
        self.is_self = self.user_id == app.user.user_id
        self.frame = tk.Frame(parent, bg=COLORS["page"], padx=20, pady=14)
        self.name_var = tk.StringVar(value=app.user.full_name)
        self.password_vars = {name: tk.StringVar() for name in ("current", "new", "confirm")}
        self.name_message = tk.StringVar()
        self.password_message = tk.StringVar()
        self.admin_message = tk.StringVar()
        self.stat_vars = {name: tk.StringVar(value="0") for name in ("total", "ADD", "UPDATE", "DELETE")}
        self.row = None
        self.build()
        self.load()

    # ------------------------------------------------------------------ layout

    def build(self):
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)

        left = tk.Frame(self.frame, bg=COLORS["page"], width=330)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        left.pack_propagate(False)
        right = tk.Frame(self.frame, bg=COLORS["page"])
        right.grid(row=0, column=1, sticky="nsew")

        self.build_identity(left)
        if self.is_self:
            self.build_settings(left)
        else:
            self.build_admin_controls(left)

        mine = "My " if self.is_self else ""
        stat_tiles(right, (
            ("total", f"{mine}Product Changes", "strong"),
            ("ADD", "Products Added", "green"),
            ("UPDATE", "Products Updated", "primary"),
            ("DELETE", "Products Deleted", "red"),
        ), self.stat_vars)

        outer, card = panel(right, padx=0, pady=0)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        top = card_header(card, f"{mine}Activity", "Newest first")
        self.history_count = tk.Label(top, bg=COLORS["primary_soft"], fg=COLORS["primary"], font=sans(8, "bold"), padx=6, pady=1)
        self.history_count.pack(side=tk.LEFT, padx=(10, 0))
        self.history = table(card, (
            ("time", "When", 165, tk.W),
            ("action", "Action", 95, tk.W),
            ("details", "Details", 470, tk.W),
        ), height=8)

    def build_identity(self, parent):
        outer, card = panel(parent)
        outer.pack(fill=tk.X)
        if not self.is_self:
            back = tk.Label(card, text="‹  Back to Admin Dashboard", bg=COLORS["card"], fg=COLORS["primary"], font=sans(8, "bold"), cursor="hand2")
            back.pack(anchor=tk.W, pady=(0, 8))
            back.bind("<Button-1>", lambda event: self.app.show_page("admin"))
        row = tk.Frame(card, bg=COLORS["card"])
        row.pack(fill=tk.X)
        self.avatar = tk.Canvas(row, width=58, height=58, bg=COLORS["card"], highlightthickness=0)
        self.avatar.pack(side=tk.LEFT)
        names = tk.Frame(row, bg=COLORS["card"])
        names.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)
        self.full_name_label = tk.Label(names, bg=COLORS["card"], fg=COLORS["strong"], font=sans(14, "bold"), anchor=tk.W)
        self.full_name_label.pack(fill=tk.X)
        line = tk.Frame(names, bg=COLORS["card"])
        line.pack(fill=tk.X)
        self.username_label = tk.Label(line, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9, "bold"))
        self.username_label.pack(side=tk.LEFT)
        self.badge_holder = tk.Frame(line, bg=COLORS["card"])
        self.badge_holder.pack(side=tk.LEFT, padx=(8, 0))

        facts = tk.Frame(card, bg=COLORS["card"])
        facts.pack(fill=tk.X, pady=(12, 0))
        self.fact_labels = {}
        for name in ("User ID", "Date Created", "Last Sign In", "Last Update"):
            line = tk.Frame(facts, bg=COLORS["card"])
            line.pack(fill=tk.X, pady=1)
            tk.Label(line, text=name, bg=COLORS["card"], fg=COLORS["muted"], font=sans(8)).pack(side=tk.LEFT)
            value = tk.Label(line, bg=COLORS["card"], fg=COLORS["text"], font=sans(8, "bold"))
            value.pack(side=tk.RIGHT)
            self.fact_labels[name] = value

    def build_settings(self, parent):
        outer, card = panel(parent)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        caps(card, "Edit Profile", color=COLORS["primary"], size=9).pack(anchor=tk.W)
        self.name_entry = self.field(card, "Full Name", self.name_var)
        self.name_note = self.message_label(card)
        FlatButton(
            card, "Save Name", self.save_name, COLORS["card_high"], COLORS["strong"], COLORS["card_top"],
            font_size=8, pady=6, border=COLORS["line_high"],
        ).pack(fill=tk.X, pady=(8, 0))

        tk.Frame(card, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=12)
        caps(card, "Change Password", color=COLORS["primary"], size=9).pack(anchor=tk.W)
        self.password_entries = {
            "current": self.field(card, "Current Password", self.password_vars["current"], secret=True),
            "new": self.field(card, "New Password", self.password_vars["new"], secret=True, hint="8+ chars, a letter and a number"),
            "confirm": self.field(card, "Confirm New Password", self.password_vars["confirm"], secret=True),
        }
        self.password_note = self.message_label(card)
        FlatButton(
            card, "Change Password", self.save_password, COLORS["button"], COLORS["button_text"], COLORS["primary_hover"],
            font_size=8, pady=7, border=COLORS["button"],
        ).pack(fill=tk.X, pady=(8, 0))

    def build_admin_controls(self, parent):
        outer, card = panel(parent)
        outer.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        caps(card, "Manage Account", color=COLORS["primary"], size=9).pack(anchor=tk.W)
        tk.Label(
            card, text="Only admins can see this panel. Every change here is saved in the activity log.",
            bg=COLORS["card"], fg=COLORS["muted"], font=sans(8), wraplength=290, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 10))
        self.role_button = FlatButton(card, "", self.toggle_role, COLORS["card_high"], COLORS["strong"], COLORS["card_top"],
                                      font_size=8, pady=7, border=COLORS["line_high"])
        self.role_button.pack(fill=tk.X)
        self.active_button = FlatButton(card, "", self.toggle_active, COLORS["red_soft"], COLORS["red"], COLORS["red_hover"],
                                        font_size=8, pady=7, border=COLORS["red_line"])
        self.active_button.pack(fill=tk.X, pady=(8, 0))
        FlatButton(card, "Reset Password", self.reset_password, COLORS["card_high"], COLORS["strong"], COLORS["card_top"],
                   font_size=8, pady=7, border=COLORS["line_high"]).pack(fill=tk.X, pady=(8, 0))
        self.admin_note = self.message_label(card)
        tk.Label(
            card, text="Reset Password gives this person a temporary password. Tell it to them in person; they can change it in My Dashboard.",
            bg=COLORS["card"], fg=COLORS["faint"], font=sans(8), wraplength=290, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(10, 0))

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

    def message_label(self, parent):
        anchor = tk.Frame(parent, bg=COLORS["card"])
        anchor.pack(fill=tk.X)
        return tk.Label(anchor, font=sans(8, "bold"), wraplength=280, justify=tk.LEFT, anchor=tk.W, padx=8, pady=4)

    def set_message(self, label, text, kind="error"):
        if not text:
            label.pack_forget()
            return
        icon = "✓" if kind == "success" else "⚠"
        soft, fg = ("green_soft", "green") if kind == "success" else ("red_soft", "red")
        label.configure(text=f"{icon}  {text}", bg=COLORS[soft], fg=COLORS[fg])
        label.pack(fill=tk.X, pady=(8, 0))

    # ---------------------------------------------------------------- data

    def load(self):
        try:
            self.row = database.get_user_by_id(self.user_id)
            stats = database.get_user_stats(self.user_id)
            history = database.get_user_activity(self.user_id, 300)
        except sqlite3.DatabaseError:
            self.app.database_problem("load the profile")
            return
        if self.row is None:
            self.app.show_page("admin")
            return
        row = self.row
        full_name = row["full_name"]

        self.avatar.delete("all")
        self.avatar.create_oval(2, 2, 56, 56, fill=COLORS["primary_soft"], outline=COLORS["primary_line"], width=2)
        self.avatar.create_text(29, 29, text=initials(full_name), fill=COLORS["primary"], font=sans(16, "bold"))
        self.full_name_label.configure(text=full_name if len(full_name) <= 24 else full_name[:23] + "…")
        self.username_label.configure(text=f"@{row['username']}")
        for widget in self.badge_holder.winfo_children():
            widget.destroy()
        role_badge(self.badge_holder, row["role"], bool(row["is_active"])).pack(side=tk.LEFT)

        self.fact_labels["User ID"].configure(text=f"U{row['user_id']:03d}")
        self.fact_labels["Date Created"].configure(text=nice_time(row["created_at"], "--"))
        if self.is_self:
            self.fact_labels["Last Sign In"].configure(text=nice_time(self.app.user.last_login, "None"))
        else:
            self.fact_labels["Last Sign In"].configure(text=nice_time(row["last_login"]))
        self.fact_labels["Last Update"].configure(text=nice_time(stats["last_change"], "None"))

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

        if not self.is_self:
            is_admin = row["role"] == "admin"
            self.role_button.configure(text="Set as Staff" if is_admin else "Set as Admin")
            self.active_button.configure(text="Deactivate Account" if row["is_active"] else "Activate Account")

    # ---------------------------------------------------------------- my own profile

    def save_name(self):
        self.set_message(self.name_note, "")
        try:
            self.app.user = auth.change_full_name(self.app.user, self.name_var.get())
        except ValidationError as error:
            self.set_message(self.name_note, error.message)
            self.name_entry.focus_set()
            return
        except sqlite3.DatabaseError:
            self.app.database_problem("save your name")
            return
        self.app.on_profile_changed()

    def save_password(self):
        self.set_message(self.password_note, "")
        values = {name: var.get() for name, var in self.password_vars.items()}
        try:
            auth.change_password(self.app.user, values["current"], values["new"], values["confirm"])
        except ValidationError as error:
            self.set_message(self.password_note, error.message)
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
        self.set_message(self.password_note, "Password changed. Use the new one next time you sign in.", "success")
        self.app.log("PASSWORD", "Password changed.")
        self.load()

    # ---------------------------------------------------------------- admin controls

    def run_admin_action(self, action, success):
        self.set_message(self.admin_note, "")
        try:
            result = action()
        except ValidationError as error:
            self.set_message(self.admin_note, error.message)
            return None
        except sqlite3.DatabaseError:
            self.app.database_problem("change this account")
            return None
        self.load()
        self.set_message(self.admin_note, success if isinstance(success, str) else success(result), "success")
        return result

    def toggle_role(self):
        new_role = "staff" if self.row["role"] == "admin" else "admin"
        name = self.row["full_name"]
        if not messagebox.askyesno("Change Role", f"Set {name} as {'Admin' if new_role == 'admin' else 'Staff'}?", parent=self.app.root):
            return
        self.run_admin_action(
            lambda: auth.admin_set_role(self.app.user, self.user_id, new_role),
            f"{name} is now {'an Admin' if new_role == 'admin' else 'Staff'}.",
        )

    def toggle_active(self):
        turn_on = not self.row["is_active"]
        name = self.row["full_name"]
        question = f"Activate the account of {name}?" if turn_on else f"Deactivate the account of {name}?\n\nThey will not be able to sign in until it is activated again."
        if not messagebox.askyesno("Account", question, parent=self.app.root):
            return
        self.run_admin_action(
            lambda: auth.admin_set_active(self.app.user, self.user_id, turn_on),
            f"The account was {'activated' if turn_on else 'deactivated'}.",
        )

    def reset_password(self):
        name = self.row["full_name"]
        if not messagebox.askyesno("Reset Password", f"Give {name} a new temporary password?\n\nTheir old password will stop working.", parent=self.app.root):
            return
        self.run_admin_action(
            lambda: auth.admin_reset_password(self.app.user, self.user_id),
            lambda temporary: f"Temporary password: {temporary}  (tell it to {name.split()[0]} in person)",
        )
