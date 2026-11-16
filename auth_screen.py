"""The Sign In and Create Account screen shown before the inventory opens."""

import sqlite3
import tkinter as tk

import auth
import database
import theme
from theme import COLORS, FlatButton
from validation import MIN_PASSWORD_LENGTH, ValidationError, validate_username


def sans(size, weight="normal"):
    return (theme.FONT, size, weight)


FEATURES = (
    ("▦", "Track every product", "Add, search, update, and delete items in one screen."),
    ("▲", "Catch low stock early", "Low and out of stock items are flagged right away."),
    ("⛁", "Every change is recorded", "Each change is saved with the name of the user who made it."),
)


class AuthScreen:
    def __init__(self, root, on_success, mode=None):
        self.root = root
        self.on_success = on_success
        self.mode = mode or ("sign_in" if database.count_users() else "sign_up")
        self.show_password = False
        self.busy = False

        self.vars = {name: tk.StringVar() for name in ("full_name", "username", "password", "confirm")}
        self.error_var = tk.StringVar()
        self.message_kind = "error"  # "error" (red) or "success" (green) for the message under the form
        self.entries = {}
        for name in ("username", "password", "confirm"):
            self.vars[name].trace_add("write", lambda *args: self.check_as_you_type())

        self.root.title("Sign In - Product Inventory System")
        self.build()

    # ------------------------------------------------------------------ layout

    def build(self):
        self.frame = tk.Frame(self.root, bg=COLORS["page"])
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.build_brand_panel()
        self.build_form_side()

    def build_brand_panel(self):
        panel = tk.Frame(self.frame, bg=COLORS["sidebar"], width=470)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)
        tk.Frame(self.frame, bg=COLORS["line"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(panel, bg=COLORS["sidebar"], padx=48)
        inner.place(relx=0, rely=0.5, anchor=tk.W, relwidth=1)

        logo = tk.Canvas(inner, width=56, height=56, bg=COLORS["sidebar"], highlightthickness=0)
        logo.pack(anchor=tk.W)
        logo.create_rectangle(1, 1, 55, 55, fill=COLORS["card_high"], outline=COLORS["primary_line"])
        logo.create_polygon(28, 11, 43, 19, 28, 27, 13, 19, fill=COLORS["primary"], outline="")
        logo.create_polygon(13, 23, 26, 30, 26, 45, 13, 38, fill=COLORS["primary"], outline="")
        logo.create_polygon(43, 23, 30, 30, 30, 45, 43, 38, fill=COLORS["primary_hover"], outline="")

        tk.Label(inner, text="IM102", bg=COLORS["sidebar"], fg=COLORS["primary"], font=sans(10, "bold")).pack(anchor=tk.W, pady=(22, 0))
        tk.Label(
            inner, text="Product Inventory\nSystem", bg=COLORS["sidebar"], fg=COLORS["strong"], font=sans(26, "bold"), justify=tk.LEFT,
        ).pack(anchor=tk.W)
        tk.Label(
            inner,
            text="Keep your stock organized, see what needs restocking, and know who changed what.",
            bg=COLORS["sidebar"], fg=COLORS["muted"], font=sans(10), justify=tk.LEFT, wraplength=360,
        ).pack(anchor=tk.W, pady=(10, 26))

        for icon, title, text in FEATURES:
            row = tk.Frame(inner, bg=COLORS["sidebar"])
            row.pack(fill=tk.X, pady=7)
            tk.Label(
                row, text=icon, bg=COLORS["card_high"], fg=COLORS["primary"], font=sans(12), width=3, pady=4,
                highlightthickness=1, highlightbackground=COLORS["line_high"],
            ).pack(side=tk.LEFT, anchor=tk.N)
            words = tk.Frame(row, bg=COLORS["sidebar"])
            words.pack(side=tk.LEFT, padx=(14, 0))
            tk.Label(words, text=title, bg=COLORS["sidebar"], fg=COLORS["text"], font=sans(10, "bold")).pack(anchor=tk.W)
            tk.Label(words, text=text, bg=COLORS["sidebar"], fg=COLORS["muted"], font=sans(9), wraplength=300, justify=tk.LEFT).pack(anchor=tk.W)

    def build_form_side(self):
        side = tk.Frame(self.frame, bg=COLORS["page"])
        side.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        top = tk.Frame(side, bg=COLORS["page"], padx=24, pady=16)
        top.pack(fill=tk.X)
        FlatButton(
            top, "Light Mode" if theme.MODE == "dark" else "Dark Mode", self.toggle_theme,
            COLORS["card_high"], COLORS["text"], COLORS["card_top"], font_size=8, pady=6,
            border=COLORS["line_high"], hover_fg=COLORS["strong"],
        ).pack(side=tk.RIGHT)

        holder = tk.Frame(side, bg=COLORS["page"])
        holder.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        outer = tk.Frame(holder, bg=COLORS["line"])
        outer.pack()
        self.card = tk.Frame(outer, bg=COLORS["card"], padx=34, pady=24, width=420)
        self.card.pack(padx=1, pady=1)

        self.build_tabs()
        self.form_area = tk.Frame(self.card, bg=COLORS["card"])
        self.form_area.pack(fill=tk.X)
        self.build_fields()

        tk.Label(
            holder, text="Passwords are stored as salted PBKDF2-SHA256 hashes, never as plain text.",
            bg=COLORS["page"], fg=COLORS["faint"], font=sans(8),
        ).pack(pady=(12, 0))

    def build_tabs(self):
        tabs = tk.Frame(self.card, bg=COLORS["input"], padx=3, pady=3, highlightthickness=1, highlightbackground=COLORS["line_high"])
        tabs.pack(fill=tk.X, pady=(0, 18))
        tabs.columnconfigure((0, 1), weight=1, uniform="tabs")
        for column, (mode, text) in enumerate((("sign_in", "Sign In"), ("sign_up", "Create Account"))):
            active = mode == self.mode
            FlatButton(
                tabs, text, lambda value=mode: self.switch_mode(value),
                COLORS["card_high"] if active else COLORS["input"],
                COLORS["strong"] if active else COLORS["muted"],
                COLORS["card_high"] if active else COLORS["card"],
                font_size=9, pady=7, hover_fg=COLORS["strong"],
            ).grid(row=0, column=column, sticky="ew")
        self.tabs = tabs

    def build_fields(self):
        for widget in self.form_area.winfo_children():
            widget.destroy()
        self.entries = {}
        area = self.form_area
        signing_up = self.mode == "sign_up"

        title = "Create your account" if signing_up else "Welcome back"
        subtitle = (
            "Sign up to start managing the inventory."
            if signing_up
            else "Sign in with your username and password to continue."
        )
        tk.Label(area, text=title, bg=COLORS["card"], fg=COLORS["strong"], font=sans(18, "bold")).pack(anchor=tk.W)
        tk.Label(area, text=subtitle, bg=COLORS["card"], fg=COLORS["muted"], font=sans(9), wraplength=340, justify=tk.LEFT).pack(
            anchor=tk.W, pady=(2, 6)
        )

        if signing_up:
            self.add_field("full_name", "Full Name")
        self.add_field("username", "Username", hint="3-20 letters, numbers, . or _" if signing_up else None)
        self.add_field("password", "Password", secret=True,
                       hint=f"{MIN_PASSWORD_LENGTH}+ characters, a letter and a number" if signing_up else None)
        if signing_up:
            self.add_field("confirm", "Confirm Password", secret=True)

        toggle_row = tk.Frame(area, bg=COLORS["card"])
        toggle_row.pack(fill=tk.X, pady=(10, 0))
        self.show_toggle = tk.Label(toggle_row, bg=COLORS["card"], fg=COLORS["dim"], font=sans(9), cursor="hand2")
        self.show_toggle.pack(side=tk.LEFT)
        self.show_toggle.bind("<Button-1>", lambda event: self.toggle_password())
        self.caps_label = tk.Label(toggle_row, text="", bg=COLORS["card"], fg=COLORS["amber"], font=sans(8, "bold"))
        self.caps_label.pack(side=tk.RIGHT)
        self.update_password_visibility()

        self.error_anchor = tk.Frame(area, bg=COLORS["card"])
        self.error_anchor.pack(fill=tk.X)
        self.error_label = tk.Label(
            self.error_anchor, textvariable=self.error_var, bg=COLORS["red_soft"], fg=COLORS["red"], font=sans(9, "bold"),
            wraplength=330, justify=tk.LEFT, anchor=tk.W, padx=10, pady=7,
        )
        self.show_or_hide_error()

        self.submit_button = FlatButton(
            area, "Create Account" if signing_up else "Sign In", self.submit,
            COLORS["button"], COLORS["button_text"], COLORS["primary_hover"], font_size=10, pady=10, border=COLORS["button"],
        )
        self.submit_button.pack(fill=tk.X, pady=(16, 0))

        switch = tk.Frame(area, bg=COLORS["card"])
        switch.pack(pady=(14, 0))
        tk.Label(
            switch, text="Already have an account?" if signing_up else "New here?", bg=COLORS["card"], fg=COLORS["muted"], font=sans(9),
        ).pack(side=tk.LEFT)
        link = tk.Label(
            switch, text="Sign in" if signing_up else "Create an account", bg=COLORS["card"], fg=COLORS["primary"],
            font=sans(9, "bold"), cursor="hand2",
        )
        link.pack(side=tk.LEFT, padx=(4, 0))
        link.bind("<Button-1>", lambda event: self.switch_mode("sign_in" if signing_up else "sign_up"))

        self.check_as_you_type()
        first = "full_name" if signing_up else "username"
        if self.mode == "sign_in" and self.vars["username"].get():
            first = "password"
        self.root.after_idle(lambda: self.entries[first].winfo_exists() and self.entries[first].focus_set())

    def add_field(self, name, label, secret=False, hint=None):
        wrapper = tk.Frame(self.form_area, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(12, 0))
        top = tk.Frame(wrapper, bg=COLORS["card"])
        top.pack(fill=tk.X)
        tk.Label(top, text=label, bg=COLORS["card"], fg=COLORS["dim"], font=sans(8, "bold")).pack(side=tk.LEFT)
        # The right side of the label row shows the hint, or a live message like "Passwords do not match".
        note = tk.Label(top, text=hint or "", bg=COLORS["card"], fg=COLORS["faint"], font=sans(8))
        note.pack(side=tk.RIGHT)
        box = tk.Frame(wrapper, bg=COLORS["input"], highlightthickness=1, highlightbackground=COLORS["line_high"])
        box.pack(fill=tk.X, pady=(4, 0))
        entry = tk.Entry(
            box, textvariable=self.vars[name], width=36, bg=COLORS["input"], fg=COLORS["text"],
            insertbackground=COLORS["primary"], selectbackground=COLORS["primary"], selectforeground=COLORS["button_text"],
            relief=tk.FLAT, bd=0, highlightthickness=0, font=sans(10),
        )
        entry.pack(fill=tk.X, ipady=7, padx=10)
        entry.secret = secret
        entry.box = box
        entry.note = note
        entry.hint = hint or ""
        entry.problem = False
        entry.bind("<FocusIn>", lambda e: box.configure(highlightbackground=COLORS["primary"]), add="+")
        entry.bind("<FocusOut>", lambda e, en=entry: box.configure(highlightbackground=COLORS["red"] if en.problem else COLORS["line_high"]), add="+")
        entry.bind("<Return>", lambda event: self.submit())
        entry.bind("<KeyRelease>", self.check_caps_lock, add="+")
        entry.bind("<Key>", lambda event: self.message_kind == "error" and self.error_var.get() and self.clear_error(), add="+")
        self.entries[name] = entry

    def set_note(self, name, text=None, kind=None):
        """Show a live message next to a box label: kind "error" (red), "ok" (green), or None for the normal hint."""
        entry = self.entries.get(name)
        if entry is None or not entry.winfo_exists():
            return
        if kind is None:
            entry.note.configure(text=entry.hint, fg=COLORS["faint"], font=sans(8))
        else:
            entry.note.configure(text=text, fg=COLORS["red"] if kind == "error" else COLORS["green"], font=sans(8, "bold"))
        entry.problem = kind == "error"
        if entry.focus_get() is not entry:
            entry.box.configure(highlightbackground=COLORS["red"] if entry.problem else COLORS["line_high"])

    def check_as_you_type(self):
        """On Create Account, say right away if the username is taken or the two passwords do not match."""
        if self.mode != "sign_up" or "confirm" not in self.entries:
            return

        username = self.vars["username"].get()
        try:
            validate_username(username)
        except ValidationError:
            self.set_note("username")  # Not finished yet: keep the normal hint. Wrong format is shown on Create Account.
        else:
            try:
                taken = database.get_user_by_username(username) is not None
            except sqlite3.DatabaseError:
                taken = False
            if taken:
                self.set_note("username", "✗  Username is already taken", "error")
            else:
                self.set_note("username", "✓  Username is available", "ok")

        password, confirm = self.vars["password"].get(), self.vars["confirm"].get()
        if not confirm:
            self.set_note("confirm")
        elif confirm != password:
            self.set_note("confirm", "✗  Passwords do not match", "error")
        else:
            self.set_note("confirm", "✓  Passwords match", "ok")

    # ---------------------------------------------------------------- behavior

    def show_or_hide_error(self):
        if not self.error_label.winfo_exists():
            return
        if self.message_kind == "success":
            self.error_label.configure(bg=COLORS["green_soft"], fg=COLORS["green"])
        else:
            self.error_label.configure(bg=COLORS["red_soft"], fg=COLORS["red"])
        if self.error_var.get():
            self.error_label.pack(fill=tk.X, pady=(12, 0))
        else:
            self.error_label.pack_forget()

    def show_error(self, message, field=None):
        self.message_kind = "error"
        self.error_var.set(f"⚠  {message}")
        self.show_or_hide_error()
        entry = self.entries.get(field)
        if entry is not None:
            entry.box.configure(highlightbackground=COLORS["red"])
            entry.focus_set()
            entry.select_range(0, tk.END)
            entry.bind("<FocusOut>", lambda e, en=entry: en.box.configure(highlightbackground=COLORS["red"] if en.problem else COLORS["line_high"]), add="")

    def clear_error(self):
        self.error_var.set("")
        self.show_or_hide_error()

    def update_password_visibility(self):
        for entry in self.entries.values():
            if entry.secret:
                entry.configure(show="" if self.show_password else "•")
        self.show_toggle.configure(text=("☑  Show password" if self.show_password else "☐  Show password"))

    def toggle_password(self):
        self.show_password = not self.show_password
        self.update_password_visibility()

    def check_caps_lock(self, event):
        # Bit 2 of the event state is Caps Lock on Windows and Linux.
        caps_on = bool(event.state & 0x2)
        if hasattr(self, "caps_label") and self.caps_label.winfo_exists():
            self.caps_label.configure(text="Caps Lock is on" if caps_on else "")

    def switch_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self.vars["password"].set("")
        self.vars["confirm"].set("")
        self.error_var.set("")
        self.message_kind = "error"
        self.tabs.destroy()
        self.form_area.destroy()
        self.build_tabs()
        self.form_area = tk.Frame(self.card, bg=COLORS["card"])
        self.form_area.pack(fill=tk.X)
        self.build_fields()

    def toggle_theme(self):
        theme.set_mode("light" if theme.MODE == "dark" else "dark")
        theme.apply_ttk_theme(self.root)
        self.frame.destroy()
        self.build()

    def submit(self):
        if self.busy:
            return
        self.busy = True
        self.submit_button.set_enabled(False)
        self.root.update_idletasks()
        values = {name: var.get() for name, var in self.vars.items()}
        try:
            if self.mode == "sign_up":
                user = auth.sign_up(values["full_name"], values["username"], values["password"], values["confirm"])
            else:
                user = auth.sign_in(values["username"], values["password"])
        except ValidationError as error:
            self.busy = False
            self.submit_button.set_enabled(True)
            if error.field == "password" and self.mode == "sign_in":
                self.vars["password"].set("")
            self.show_error(error.message, error.field)
            return
        except Exception:
            self.busy = False
            self.submit_button.set_enabled(True)
            raise

        self.busy = False
        self.vars["password"].set("")
        self.vars["confirm"].set("")

        if self.mode == "sign_up":
            # A new account does not sign in by itself: the user signs in with the details they just made.
            self.vars["full_name"].set("")
            self.vars["username"].set(user.username)
            self.switch_mode("sign_in")
            self.show_success(f"Account created for {user.full_name}. Please sign in with your new username and password.")
            return

        self.destroy()
        self.on_success(user)

    def show_success(self, message):
        self.message_kind = "success"
        self.error_var.set(f"✓  {message}")
        self.show_or_hide_error()

    def destroy(self):
        if self.frame.winfo_exists():
            self.frame.destroy()
