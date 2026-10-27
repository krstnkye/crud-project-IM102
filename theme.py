import json
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk


PALETTES = {
    "dark": {
        "page": "#000000",
        "card": "#09090b",
        "card_high": "#131318",
        "input": "#101014",
        "line": "#242424",
        "line_high": "#3a3a3a",
        "text": "#dddddd",
        "strong": "#ffffff",
        "muted": "#8a8a8a",
        "faint": "#555555",
        "primary": "#aa88ff",
        "primary_hover": "#c2a8ff",
        "primary_soft": "#1b152b",
        "primary_line": "#3b2d63",
        "button": "#ffffff",
        "button_text": "#000000",
        "green": "#34d399",
        "green_soft": "#0b1f17",
        "amber": "#ffaa55",
        "amber_soft": "#241a12",
        "red": "#ff4466",
        "red_soft": "#170a0e",
        "red_hover": "#2b1018",
        "red_line": "#441a23",
        "row_alt": "#060608",
        "row_low": "#14070b",
        "selected": "#1d1730",
    },
    "light": {
        "page": "#f3f3f6",
        "card": "#ffffff",
        "card_high": "#ededf2",
        "input": "#fafafc",
        "line": "#dcdce3",
        "line_high": "#c4c4cf",
        "text": "#222228",
        "strong": "#000000",
        "muted": "#6b6b76",
        "faint": "#a0a0aa",
        "primary": "#6a43e8",
        "primary_hover": "#5532d1",
        "primary_soft": "#efe9ff",
        "primary_line": "#cdbdff",
        "button": "#111111",
        "button_text": "#ffffff",
        "green": "#047857",
        "green_soft": "#e3f8ef",
        "amber": "#b45309",
        "amber_soft": "#fff1e2",
        "red": "#d6204a",
        "red_soft": "#ffedf1",
        "red_hover": "#ffd9e1",
        "red_line": "#f5b5c3",
        "row_alt": "#f8f8fb",
        "row_low": "#fff2f5",
        "selected": "#e9e1ff",
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


FONT_CHOICES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Helvetica")
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
        font=(MONO, 9),
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
        font=(MONO, 8, "bold"),
        relief=tk.FLAT,
        borderwidth=0,
        padding=(8, 8),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["line"])],
        foreground=[("active", COLORS["primary"])],
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
        padding=(8, 5),
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
    root.option_add("*TCombobox*Listbox.font", (MONO, 10))
    root.option_add("*TCombobox*Listbox.relief", "flat")


class FlatButton(tk.Label):
    """A flat button with hover colors that looks the same on Windows, macOS, and Linux."""

    def __init__(self, parent, text, command, bg, fg, hover_bg=None, font_size=9, padx=14, pady=8, border=None, hover_fg=None):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(MONO, font_size, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1 if border else 0,
            highlightbackground=border or bg,
        )
        self.command = command
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
            self.configure(bg=self.colors[0], fg=self.colors[1], cursor="hand2")
        else:
            self.configure(bg=COLORS["card_high"], fg=COLORS["faint"], cursor="arrow")
