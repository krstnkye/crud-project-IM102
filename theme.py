import json
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk


PALETTES = {
    "dark": {
        "page": "#0e1014",
        "card": "#161920",
        "card_high": "#1e222b",
        "input": "#11141a",
        "line": "#272c36",
        "line_high": "#363c48",
        "text": "#d6dae2",
        "strong": "#f5f7fb",
        "muted": "#8b93a3",
        "faint": "#5d6473",
        "primary": "#7c6cff",
        "primary_hover": "#9183ff",
        "primary_soft": "#211e3a",
        "primary_line": "#3c3672",
        "button": "#7c6cff",
        "button_text": "#ffffff",
        "green": "#3ecf8e",
        "green_soft": "#11261d",
        "amber": "#f5a524",
        "amber_soft": "#2a2112",
        "red": "#f2555a",
        "red_soft": "#2a1517",
        "red_hover": "#3a1b1e",
        "red_line": "#5a2a2e",
        "row_alt": "#181c23",
        "row_low": "#272012",
        "row_out": "#2e1a1c",
        "selected": "#2b2756",
    },
    "light": {
        "page": "#f3f4f7",
        "card": "#ffffff",
        "card_high": "#f2f3f7",
        "input": "#ffffff",
        "line": "#e2e5eb",
        "line_high": "#cdd2db",
        "text": "#2a2f39",
        "strong": "#0f1218",
        "muted": "#687082",
        "faint": "#9aa1ae",
        "primary": "#5b4cf0",
        "primary_hover": "#4a3bdc",
        "primary_soft": "#efedff",
        "primary_line": "#cbc5ff",
        "button": "#5b4cf0",
        "button_text": "#ffffff",
        "green": "#13855c",
        "green_soft": "#e5f6ee",
        "amber": "#b06a00",
        "amber_soft": "#fff3df",
        "red": "#d6363c",
        "red_soft": "#fdeced",
        "red_hover": "#fadadb",
        "red_line": "#f2b8ba",
        "row_alt": "#fafbfc",
        "row_low": "#fff6e3",
        "row_out": "#fdeeee",
        "selected": "#e8e5ff",
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


FONT_CHOICES = ("Segoe UI", "Segoe UI Variable Text", "Inter", "SF Pro Text", "Helvetica Neue", "DejaVu Sans", "Helvetica")
MONO_CHOICES = ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "JetBrains Mono", "DejaVu Sans Mono", "Courier")

FONT = "Helvetica"
MONO = "Courier"


def load_fonts(root):
    """Pick the nicest font that is installed on this computer."""
    global FONT, MONO
    installed = set(tkfont.families(root))
    FONT = next((name for name in FONT_CHOICES if name in installed), FONT)
    MONO = next((name for name in MONO_CHOICES if name in installed), MONO)


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
        foreground=COLORS["muted"],
        font=(FONT, 9, "bold"),
        relief=tk.FLAT,
        borderwidth=0,
        padding=(10, 9),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["card_high"])],
        foreground=[("active", COLORS["strong"])],
    )
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["line"],
        troughcolor=COLORS["card"],
        bordercolor=COLORS["card"],
        arrowcolor=COLORS["muted"],
        lightcolor=COLORS["line"],
        darkcolor=COLORS["line"],
        gripcount=0,
        arrowsize=12,
    )
    style.map("Vertical.TScrollbar", background=[("active", COLORS["primary"])])

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["input"],
        background=COLORS["card_high"],
        foreground=COLORS["strong"],
        arrowcolor=COLORS["primary"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["input"],
        darkcolor=COLORS["input"],
        selectbackground=COLORS["input"],
        selectforeground=COLORS["strong"],
        insertcolor=COLORS["strong"],
        padding=(10, 7),
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
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.relief", "flat")


class FlatButton(tk.Label):
    """A flat button with hover colors that looks the same on Windows, macOS, and Linux."""

    def __init__(self, parent, text, command, bg, fg, hover_bg=None, font_size=10, padx=16, pady=9, border=None, hover_fg=None, weight="bold"):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(FONT, font_size, weight),
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
