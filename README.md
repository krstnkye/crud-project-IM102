# Product Inventory System

This is a simple IM102 project made with Python, Tkinter, and SQLite.

The app helps you keep a list of products. You can add a product, see the saved products, change product details, and delete products you no longer need.

The top part of the app shows:

- Total Products
- Total Stock
- Low Stock
- Total Value

## What You Need

- Python 3.10 or newer
- Tkinter, which usually comes with Python
- No extra packages are needed

## Folder Structure

```text
InventoryManagement/
|-- main.py
|-- database.py
|-- database_viewer.py
|-- theme.py
|-- inventory.db (created automatically after the app starts)
|-- README.md
|-- .gitignore
|-- documentation/
|   |-- Product_Inventory_System_Documentation.docx
|   |-- Project_Report.md
|   |-- Project_Report.pdf
|   |-- flowchart.mmd
|   |-- build_final_documentation.py
|   `-- generate_report_pdf.py
`-- screenshots/
    `-- README.md
```

`inventory.db` is the saved product file. It is made automatically when the app runs and is not uploaded to GitHub, so each user starts with an empty product list.

## How To Run

1. Open the `InventoryManagement` folder in VS Code or IDLE.
2. Open a terminal in that folder.
3. Run:

```bash
python main.py
```

If your computer uses the Python launcher, run:

```bash
py main.py
```

## Main Buttons

| Button | What It Does |
| --- | --- |
| Add Product | Saves a new product. |
| Update | Changes the selected product. |
| Delete | Removes the selected product after asking first. |
| Clear Fields | Empties the form so you can type again. |
| New Product | Clears the form and puts the cursor in Product Name. |
| DB Records | Opens a window that shows the raw rows inside `inventory.db`. |
| Light Mode / Dark Mode | Switches the app between the dark and light theme. |

Update and Delete only turn on after you click a product in the list.

## Helpful Extras

- **Dark and light mode:** click the theme button at the top (or press `Ctrl+L`). The app remembers your choice in `settings.json`, which stays on your own computer.
- **Category filter:** click a category chip above the table to show only that category.
- **Search:** type in the search box to filter products by ID, name, or category.
- **Sorting:** click a column heading to sort. Click it again to reverse the order.
- **Stock status:** products with less than 10 pieces are shown in amber, and products with 0 pieces in red.
- **Product inspector:** shows the selected product's details and a stock bar compared with the low stock line.
- **Activity log:** lists what you added, updated, or deleted while the app is open.
- **Keyboard shortcuts:** `Enter` saves the form, `Esc` clears it, `Delete` removes the selected product, `Ctrl+F` jumps to the search box, and `Ctrl+L` switches the theme.

## Product Details

| Field | Meaning |
| --- | --- |
| ID | Made by the app, shown as P001, P002, and so on. |
| Product Name | Name of the item. |
| Category | Group where the item belongs. |
| Quantity | Number of pieces available. |
| Price Each | Price of one piece. |
| Amount | Quantity multiplied by price. |

## Messages

The app shows a small notice in the bottom-right corner when:

- A product is saved
- A product is changed
- A product is deleted

A red message appears inside the form when:

- A required field is empty
- Quantity or price has an invalid value
- No product is selected before updating or deleting

Deleting a product still asks for confirmation in a pop-up first.

## Suggested Testing

1. Add a product.
2. Check if it appears in the product list.
3. Check if the totals at the top changed.
4. Try typing letters in Quantity.
5. Try a negative quantity.
6. Select a product and update it.
7. Delete a product.
8. Close and open the app again to check if saved products are still there.
