import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

import database


COLORS = {
    "page": "#f8f9ff",
    "top": "#213145",
    "top_text": "#eaf1ff",
    "bar": "#eff4ff",
    "card": "#ffffff",
    "soft": "#e5eeff",
    "soft_high": "#dce9ff",
    "line": "#c3c6d7",
    "text": "#0b1c30",
    "muted": "#586377",
    "primary": "#004ac6",
    "primary_hover": "#2563eb",
    "green": "#007d55",
    "green_soft": "#bdffdb",
    "red": "#ba1a1a",
    "red_soft": "#ffdad6",
}


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Product Inventory System")
        self.root.geometry("1120x720")
        self.root.minsize(980, 640)

        self.selected_product_id = None

        database.initialize_database()

        self.product_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value="School Supplies")
        self.quantity_var = tk.StringVar()
        self.unit_price_var = tk.StringVar()
        self.item_total_var = tk.StringVar(value="Php 0.00")

        self.total_products_var = tk.StringVar(value="0")
        self.total_stock_units_var = tk.StringVar(value="0")
        self.low_stock_products_var = tk.StringVar(value="0")
        self.total_value_var = tk.StringVar(value="Php 0.00")

        self.configure_styles()
        self.build_interface()
        self.refresh_data()

        self.quantity_var.trace_add("write", self.update_item_total)
        self.unit_price_var.trace_add("write", self.update_item_total)

    def configure_styles(self):
        self.root.configure(bg=COLORS["page"])

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 10), borderwidth=0)
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=COLORS["soft"],
            foreground=COLORS["text"],
            padding=8,
        )
        style.map("Treeview", background=[("selected", COLORS["soft_high"])], foreground=[("selected", COLORS["text"])])
        style.configure("Vertical.TScrollbar", background=COLORS["soft"], troughcolor=COLORS["page"])

    def build_interface(self):
        self.build_top_bar()

        page = tk.Frame(self.root, bg=COLORS["page"])
        page.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        self.build_heading(page)
        self.build_dashboard(page)

        content = tk.Frame(page, bg=COLORS["page"])
        content.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self.build_form(content)
        self.build_table(content)

    def build_top_bar(self):
        title_bar = tk.Frame(self.root, bg=COLORS["top"], height=34)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar,
            text="Product Inventory System",
            bg=COLORS["top"],
            fg=COLORS["top_text"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=12)

        for color in ("#ef4444", "#10b981", "#f59e0b"):
            tk.Label(title_bar, text=" ", bg=color, width=2).pack(side=tk.RIGHT, padx=(0, 6), pady=9)

        status_bar = tk.Frame(self.root, bg=COLORS["bar"], height=34, highlightbackground=COLORS["line"], highlightthickness=1)
        status_bar.pack(fill=tk.X)
        status_bar.pack_propagate(False)

        tk.Label(
            status_bar,
            text="File",
            bg=COLORS["bar"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(12, 16))
        tk.Label(
            status_bar,
            text="Edit",
            bg=COLORS["bar"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 16))
        tk.Label(
            status_bar,
            text="Help",
            bg=COLORS["bar"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT)

        tk.Label(
            status_bar,
            text="Saved file: inventory.db",
            bg=COLORS["soft"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            padx=10,
            pady=3,
        ).pack(side=tk.RIGHT, padx=12)

    def build_heading(self, parent):
        heading = tk.Frame(parent, bg=COLORS["page"])
        heading.pack(fill=tk.X)

        left = tk.Frame(heading, bg=COLORS["page"])
        left.pack(side=tk.LEFT)

        tk.Label(
            left,
            text="Product Inventory System",
            bg=COLORS["page"],
            fg=COLORS["text"],
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            left,
            text="A simple project for adding, viewing, changing, and deleting products.",
            bg=COLORS["page"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(2, 0))

        tk.Button(
            heading,
            text="Refresh List",
            command=self.refresh_data,
            bg=COLORS["soft"],
            fg=COLORS["text"],
            activebackground=COLORS["soft_high"],
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

    def build_dashboard(self, parent):
        dashboard = tk.Frame(parent, bg=COLORS["page"])
        dashboard.pack(fill=tk.X, pady=(14, 0))
        for column in range(4):
            dashboard.columnconfigure(column, weight=1)

        cards = [
            ("Total Products", self.total_products_var, "items", COLORS["primary"]),
            ("Total Stock", self.total_stock_units_var, "pieces", COLORS["green"]),
            ("Low Stock", self.low_stock_products_var, "need checking", COLORS["red"]),
            ("Total Value", self.total_value_var, "", COLORS["primary"]),
        ]

        for index, (title, value, note, accent) in enumerate(cards):
            self.create_summary_card(dashboard, index, title, value, note, accent)

    def create_summary_card(self, parent, column, title, value_var, note, accent):
        card = tk.Frame(
            parent,
            bg=COLORS["card"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))

        tk.Label(card, text=title, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        tk.Label(card, textvariable=value_var, bg=COLORS["card"], fg=COLORS["text"], font=("Consolas", 20, "bold")).pack(anchor=tk.W, pady=(4, 0))
        tk.Label(card, text=note, bg=COLORS["card"], fg=accent, font=("Segoe UI", 8)).pack(anchor=tk.W)

    def build_form(self, parent):
        form = tk.Frame(
            parent,
            bg=COLORS["card"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=16,
            pady=16,
        )
        form.grid(row=0, column=0, sticky="ns", padx=(0, 14))

        tk.Label(form, text="Product Form", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(form, text="Fill this out to save a product.", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 12))

        self.create_input(form, "Product Name", self.product_name_var)
        self.create_category_input(form)
        self.create_input(form, "Quantity", self.quantity_var)
        self.create_input(form, "Price Each", self.unit_price_var)

        total_box = tk.Frame(form, bg=COLORS["soft"], padx=10, pady=8)
        total_box.pack(fill=tk.X, pady=(12, 0))
        tk.Label(total_box, text="Amount for this product", bg=COLORS["soft"], fg=COLORS["muted"], font=("Segoe UI", 8)).pack(anchor=tk.W)
        tk.Label(total_box, textvariable=self.item_total_var, bg=COLORS["soft"], fg=COLORS["text"], font=("Consolas", 14, "bold")).pack(anchor=tk.W)

        button_grid = tk.Frame(form, bg=COLORS["card"])
        button_grid.pack(fill=tk.X, pady=(16, 0))
        button_grid.columnconfigure((0, 1), weight=1)

        self.create_button(button_grid, "Add Product", self.add_product, COLORS["primary"], "#ffffff", 0, 0)
        self.create_button(button_grid, "Update", self.update_product, COLORS["soft"], COLORS["text"], 0, 1)
        self.create_button(button_grid, "Delete", self.delete_product, COLORS["red_soft"], COLORS["red"], 1, 0)
        self.create_button(button_grid, "Clear Fields", self.clear_fields, COLORS["soft"], COLORS["muted"], 1, 1)

    def create_input(self, parent, label, variable):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(8, 0))

        tk.Label(wrapper, text=label, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        tk.Entry(
            wrapper,
            textvariable=variable,
            bg="#ffffff",
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["primary"],
            font=("Segoe UI", 10),
        ).pack(fill=tk.X, pady=(4, 0), ipady=6)

    def create_category_input(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["card"])
        wrapper.pack(fill=tk.X, pady=(8, 0))

        tk.Label(wrapper, text="Category", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        combo = ttk.Combobox(
            wrapper,
            textvariable=self.category_var,
            values=("School Supplies", "Food", "Drinks", "Cleaning", "Electronics", "Other"),
            state="normal",
            font=("Segoe UI", 10),
        )
        combo.pack(fill=tk.X, pady=(4, 0), ipady=4)

    def create_button(self, parent, text, command, bg, fg, row, column):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COLORS["primary_hover"] if bg == COLORS["primary"] else COLORS["soft_high"],
            activeforeground="#ffffff" if bg == COLORS["primary"] else fg,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)

    def build_table(self, parent):
        table_card = tk.Frame(
            parent,
            bg=COLORS["card"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=16,
            pady=16,
        )
        table_card.grid(row=0, column=1, sticky="nsew")
        table_card.rowconfigure(1, weight=1)
        table_card.columnconfigure(0, weight=1)

        header = tk.Frame(table_card, bg=COLORS["card"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew")

        tk.Label(header, text="Product List", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Click a product to change or delete it.", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        columns = ("product_id", "product_name", "category", "quantity", "unit_price", "total")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("product_id", text="ID")
        self.tree.heading("product_name", text="Product Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("quantity", text="Qty")
        self.tree.heading("unit_price", text="Price")
        self.tree.heading("total", text="Amount")

        self.tree.column("product_id", width=75, anchor=tk.CENTER)
        self.tree.column("product_name", width=230)
        self.tree.column("category", width=150)
        self.tree.column("quantity", width=70, anchor=tk.CENTER)
        self.tree.column("unit_price", width=105, anchor=tk.E)
        self.tree.column("total", width=115, anchor=tk.E)

        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(12, 0))

        self.tree.bind("<<TreeviewSelect>>", self.load_selected_product)

    def validate_inputs(self):
        product_name = self.product_name_var.get().strip()
        category = self.category_var.get().strip()
        quantity_text = self.quantity_var.get().strip()
        price_text = self.unit_price_var.get().strip()

        if not product_name:
            messagebox.showwarning("Please check", "Please enter a product name.")
            return None

        if not category:
            messagebox.showwarning("Please check", "Please enter a category.")
            return None

        try:
            quantity = int(quantity_text)
        except ValueError:
            messagebox.showwarning("Please check", "Quantity must be a whole number.")
            return None

        if quantity < 0:
            messagebox.showwarning("Please check", "Quantity cannot be negative.")
            return None

        try:
            unit_price = float(price_text)
        except ValueError:
            messagebox.showwarning("Please check", "Please enter a valid price.")
            return None

        if unit_price < 0:
            messagebox.showwarning("Please check", "Please enter a valid price.")
            return None

        return product_name, category, quantity, unit_price

    def add_product(self):
        values = self.validate_inputs()
        if values is None:
            return

        try:
            result = database.add_product(*values)
        except sqlite3.DatabaseError:
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        if result == "restocked":
            messagebox.showinfo(
                "Done",
                "A product with the same name, category, and price already exists. "
                "Its quantity was increased.",
            )
        else:
            messagebox.showinfo("Done", "Product added successfully.")

    def update_product(self):
        if self.selected_product_id is None:
            messagebox.showwarning("Please choose first", "Please select a product to update.")
            return

        values = self.validate_inputs()
        if values is None:
            return

        try:
            database.update_product(self.selected_product_id, *values)
        except sqlite3.DatabaseError:
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        messagebox.showinfo("Done", "Product updated successfully.")

    def delete_product(self):
        if self.selected_product_id is None:
            messagebox.showwarning("Please choose first", "Please select a product to delete.")
            return

        confirmed = messagebox.askyesno(
            "Delete Product",
            "Are you sure you want to delete this product?",
        )
        if not confirmed:
            return

        try:
            database.delete_product(self.selected_product_id)
        except sqlite3.DatabaseError:
            messagebox.showerror("Save Problem", "Unable to save changes. Please try again.")
            return

        self.refresh_data()
        self.clear_fields()
        messagebox.showinfo("Done", "Product deleted successfully.")

    def clear_fields(self):
        self.selected_product_id = None
        self.product_name_var.set("")
        self.category_var.set("School Supplies")
        self.quantity_var.set("")
        self.unit_price_var.set("")
        self.update_item_total()
        if hasattr(self, "tree"):
            self.tree.selection_remove(self.tree.selection())

    def load_selected_product(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0]
        values = self.tree.item(item_id, "values")

        self.selected_product_id = int(item_id)
        self.product_name_var.set(values[1])
        self.category_var.set(values[2])
        self.quantity_var.set(values[3])
        self.unit_price_var.set(values[4].replace("Php ", "").replace(",", ""))
        self.update_item_total()

    def update_item_total(self, *args):
        try:
            quantity = int(self.quantity_var.get() or 0)
            price = float(self.unit_price_var.get() or 0)
        except ValueError:
            self.item_total_var.set("Php 0.00")
            return

        self.item_total_var.set(f"Php {quantity * price:,.2f}")

    def refresh_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, product in enumerate(database.get_products()):
            product_id = product["product_id"]
            display_id = f"P{product_id:03d}"
            price = product["unit_price"]
            quantity = product["quantity"]
            total = quantity * price

            tag = "even" if index % 2 == 0 else "odd"
            self.tree.insert(
                "",
                tk.END,
                iid=str(product_id),
                values=(
                    display_id,
                    product["product_name"],
                    product["category"],
                    quantity,
                    f"Php {price:,.2f}",
                    f"Php {total:,.2f}",
                ),
                tags=(tag,),
            )

        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f6f9ff")

        totals = database.get_dashboard_totals()
        self.total_products_var.set(str(totals["total_products"]))
        self.total_stock_units_var.set(str(totals["total_stock_units"]))
        self.low_stock_products_var.set(str(totals["low_stock_products"]))
        self.total_value_var.set(f"Php {totals['total_value']:,.2f}")


def main():
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
