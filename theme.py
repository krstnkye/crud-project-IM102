import json
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk


# Colors for the dark "workstation" look and a matching light look.
PALETTES = {
    "dark": {
        "page": "#0a0d1a",         # main background
        "sidebar": "#0b0d1a",      # left side bar and footer
        "header": "#10131f",       # top bar
        "card": "#191b28",         # panels
        "card_high": "#272937",    # hover, chips, table heading
        "card_top": "#323442",
        "input": "#0b0d1a",
        "line": "#262a3a",
        "line_high": "#3b494b",
        "text": "#e1e1f3",
        "strong": "#dbfcff",
        "muted": "#849495",
        "faint": "#56636a",
        "dim": "#b9cacb",
        "primary": "#00f0ff",      # cyan accent
        "primary_hover": "#7df4ff",
        "primary_soft": "#0c2a33",
        "primary_line": "#00515a",
        "button": "#00f0ff",
        "button_text": "#00363a",
        "secondary": "#ddb7ff",    # purple
        "secondary_soft": "#2a1d3d",
        "green": "#00f0ff",
        "green_soft": "#0c2a33",
        "amber": "#ffb95f",
        "amber_soft": "#2f2414",
        "red": "#ffb4ab",
        "red_strong": "#ff5c5c",
        "red_soft": "#3a1418",
        "red_hover": "#4c1a1f",
        "red_line": "#93000a",
        "row_alt": "#0e1120",
        "row_low": "#1f1a14",
        "row_out": "#241418",
        "selected": "#003a40",
    },
    "light": {
        "page": "#f2f5f8",
        "sidebar": "#e8edf2",
        "header": "#ffffff",
        "card": "#ffffff",
        "card_high": "#eef2f6",
        "card_top": "#e2e8ee",
        "input": "#ffffff",
        "line": "#d9e0e7",
        "line_high": "#bcc7d1",
        "text": "#1d2733",
        "strong": "#06363c",
        "muted": "#5b6b75",
        "faint": "#94a1ab",
        "dim": "#3e4c56",
        "primary": "#00838c",
        "primary_hover": "#006970",
        "primary_soft": "#dff6f8",
        "primary_line": "#9fdde2",
        "button": "#00838c",
        "button_text": "#ffffff",
        "secondary": "#7b2fc0",
        "secondary_soft": "#f1e6fb",
        "green": "#00838c",
        "green_soft": "#dff6f8",
        "amber": "#a85d00",
        "amber_soft": "#fff1dc",
        "red": "#c62828",
        "red_strong": "#c62828",
        "red_soft": "#fdecec",
        "red_hover": "#fadada",
        "red_line": "#f2b8ba",
        "row_alt": "#f7f9fb",
        "row_low": "#fff7ea",
        "row_out": "#fdf0f0",
        "selected": "#d2f1f4",
    },
}

# Remembers the last theme picked on this computer (not uploaded to GitHub).
SETTINGS_PATH = Path(__file__).with_name("settings.json")


def load_saved_mode():
    try:
        mode = json.loads(SETTINGS_PATH.read_text(encoding="utf-8")).get("theme", "dark")
    except (OSError, ValueError, AttributeError):
        mode = "dark"
    return mode if mode in PALETTES else "dark"


MODE = load_saved_mode()
COLORS = dict(PALETTES[MODE])


def set_mode(mode):
    """Switch between "dark" and "light" and remember the choice."""
    global MODE
    MODE = mode
    COLORS.clear()
    COLORS.update(PALETTES[mode])
    try:
        SETTINGS_PATH.write_text(json.dumps({"theme": mode}), encoding="utf-8")
    except OSError:
        pass


# Plain, formal fonts. Segoe UI is the normal Windows font; the others are for Mac and Linux.
FONT_CHOICES = ("Segoe UI", "Open Sans", "Helvetica Neue", "Arial", "Liberation Sans", "Helvetica")
# Only used to show SQL code in the Database Records window.
CODE_CHOICES = ("Consolas", "Menlo", "Liberation Mono", "Courier New", "Courier")

FONT = "Helvetica"
TITLE = FONT
CODE = "Courier"


def load_fonts(root):
    """Pick the fonts that are available on this computer."""
    global TITLE, FONT, CODE
    installed = set(tkfont.families(root))
    FONT = next((name for name in FONT_CHOICES if name in installed), FONT)
    TITLE = FONT
    CODE = next((name for name in CODE_CHOICES if name in installed), CODE)


def apply_ttk_theme(root):
    root.configure(bg=COLORS["page"])

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        "Treeview",
        background=COLORS["card"],
        fieldbackground=COLORS["card"],
        foreground=COLORS["text"],
        rowheight=34,
        font=(FONT, 10),
        borderwidth=0,
        relief=tk.FLAT,
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["selected"])],
        foreground=[("selected", COLORS["strong"])],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["card_high"],
        foreground=COLORS["dim"],
        font=(FONT, 9, "bold"),
        relief=tk.FLAT,
        borderwidth=0,
        padding=(10, 8),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["card_top"])],
        foreground=[("active", COLORS["primary"])],
    )
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["card_high"],
        troughcolor=COLORS["card"],
        bordercolor=COLORS["card"],
        arrowcolor=COLORS["muted"],
        lightcolor=COLORS["card_high"],
        darkcolor=COLORS["card_high"],
        gripcount=0,
        arrowsize=11,
    )
    style.map("Vertical.TScrollbar", background=[("active", COLORS["primary"])])

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["input"],
        background=COLORS["card_high"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["primary"],
        bordercolor=COLORS["line_high"],
        lightcolor=COLORS["input"],
        darkcolor=COLORS["input"],
        selectbackground=COLORS["input"],
        selectforeground=COLORS["text"],
        insertcolor=COLORS["text"],
        padding=(10, 6),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["input"])],
        bordercolor=[("focus", COLORS["primary"])],
        lightcolor=[("focus", COLORS["input"])],
        darkcolor=[("focus", COLORS["input"])],
    )

    # Colors for the drop-down list that opens under the combobox.
    root.option_add("*TCombobox*Listbox.background", COLORS["card_high"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["button_text"])
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.relief", "flat")


class FlatButton(tk.Label):
    """A flat button with hover colors that looks the same on Windows, macOS, and Linux."""

    def __init__(self, parent, text, command, bg, fg, hover_bg=None, font_size=9, padx=14, pady=7, border=None, hover_fg=None, weight="bold", family=None):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(family or FONT, font_size, weight),
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1 if border else 0,
            highlightbackground=border or bg,
        )
        self.command = command
        self.border = border or bg
        self.colors = (bg, fg, hover_bg or bg, hover_fg or fg)
        self.enabled = True

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def on_enter(self, event=None):
        if self.enabled:
            self.configure(bg=self.colors[2], fg=self.colors[3])

    def on_leave(self, event=None):
        if self.enabled:
            self.configure(bg=self.colors[0], fg=self.colors[1])

    def on_click(self, event=None):
        if self.enabled:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.configure(bg=self.colors[0], fg=self.colors[1], cursor="hand2", highlightbackground=self.border)
        else:
            self.configure(bg=COLORS["card_high"], fg=COLORS["faint"], cursor="arrow", highlightbackground=COLORS["line"])
