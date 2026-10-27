import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


COLORS = {
    "page": "#0e1016",
    "sidebar": "#12141c",
    "card": "#171a24",
    "card_high": "#1e2230",
    "input": "#11131a",
    "line": "#262a38",
    "line_high": "#343a4d",
    "text": "#e8eaf2",
    "muted": "#8a91a6",
    "faint": "#5d6478",
    "primary": "#7c5cff",
    "primary_hover": "#9277ff",
    "primary_soft": "#251f45",
    "cyan": "#22d3ee",
    "cyan_soft": "#0f2e36",
    "green": "#34d399",
    "green_soft": "#0f2f25",
    "amber": "#fbbf24",
    "amber_soft": "#33280c",
    "red": "#f87171",
    "red_soft": "#3a1719",
    "row_alt": "#141721",
}

FONT_CHOICES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Helvetica")
MONO_CHOICES = ("Cascadia Mono", "Consolas", "JetBrains Mono", "SF Mono", "Menlo", "DejaVu Sans Mono", "Courier")

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
        rowheight=38,
        font=(FONT, 10),
        borderwidth=0,
        relief=tk.FLAT,
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["primary_soft"])],
        foreground=[("selected", "#ffffff")],
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
        background=[("active", COLORS["line_high"])],
        foreground=[("active", COLORS["text"])],
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
    style.map("Vertical.TScrollbar", background=[("active", COLORS["line_high"])])

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["input"],
        background=COLORS["card_high"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["input"],
        darkcolor=COLORS["input"],
        selectbackground=COLORS["input"],
        selectforeground=COLORS["text"],
        insertcolor=COLORS["text"],
        padding=(8, 6),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["input"])],
        bordercolor=[("focus", COLORS["primary"])],
        lightcolor=[("focus", COLORS["primary"])],
        darkcolor=[("focus", COLORS["primary"])],
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

    def __init__(self, parent, text, command, bg, fg, hover_bg=None, font_size=10, padx=14, pady=9):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(FONT, font_size, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
        )
        self.command = command
        self.colors = (bg, fg, hover_bg or bg)
        self.enabled = True

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def on_enter(self, event=None):
        if self.enabled:
            self.configure(bg=self.colors[2])

    def on_leave(self, event=None):
        if self.enabled:
            self.configure(bg=self.colors[0])

    def on_click(self, event=None):
        if self.enabled:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.configure(bg=self.colors[0], fg=self.colors[1], cursor="hand2")
        else:
            self.configure(bg=COLORS["card_high"], fg=COLORS["faint"], cursor="arrow")
