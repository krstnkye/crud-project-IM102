# Product Inventory System

This is a simple IM102 project made with Python, Tkinter, and SQLite.

The app helps you keep a list of products. You can add a product, see the saved products, change product details, and delete products you no longer need.

The five summary cards at the top of the app show:

- Total Inventory Value (quantity × unit price of all products)
- Registered Products, with the total number of units
- Low Stock Alerts (products with less than 10 pieces)
- Out of Stock (products with 0 pieces)
- SQLite Database (the size of `inventory.db`)

## What You Need

- Python 3.10 or newer
- Tkinter, which usually comes with Python
- No extra packages are needed

## Folder Structure

```text
crud-project-IM102/
|-- main.py
|-- database.py
|-- database_viewer.py
|-- theme.py
|-- test_database.py
|-- inventory.db (created automatically after the app starts)
|-- README.md
|-- .gitignore
|-- documentation/
|   |-- IM102_Inventory_System_Documentation.docx
|   |-- flowchart.mmd
|   `-- flowchart.png
`-- screenshots/
    |-- README.md
    `-- (pictures used in the documentation)
```

`inventory.db` is the saved product file. It is made automatically when the app runs and is not uploaded to GitHub, so each user starts with an empty product list.

## How To Run

1. Open the `crud-project-IM102` folder in VS Code or IDLE.
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
| Database Records | Opens a window that shows the raw rows inside `inventory.db`, the database details, and quick queries. It updates by itself after every change. |
| Export CSV | In the Database Records window, saves the rows shown to a CSV file you can open in Excel. |
| Light Mode / Dark Mode | Switches the app between the dark and light theme. |

Update and Delete only turn on after you click a product in the list.

## Helpful Extras

- **Dark and light mode:** click the theme button at the top (or press `Ctrl+L`). The app remembers your choice in `settings.json`, which stays on your own computer.
- **Category filter:** click a category chip above the table to show only that category.
- **Search:** type in the search box to filter products by ID, name, or category.
- **Sorting:** click a column heading to sort. Click it again to reverse the order.
- **Stock status:** products with less than 10 pieces are shown in amber, and products with 0 pieces in red.
- **Product details:** shows the selected product's stock, price, total value, status, and a stock bar compared with the low stock line.
- **Fonts:** the app uses Segoe UI, the normal Windows font. On Mac or Linux it uses a similar font that is already installed.
- **Activity log:** lists what you added, updated, or deleted while the app is open.
- **Keyboard shortcuts:** `Enter` saves the form, `Esc` clears it, `Delete` removes the selected product (click the table first), `Ctrl+F` jumps to the search box, and `Ctrl+L` switches the theme.

## Same Product Rule

If you add a product with the same name, category, and price as one that is already saved, the app does not make a second copy. It adds the new quantity to the saved product instead. Updating a product so it matches another saved product is blocked.

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

The app shows a small notice at the top of the window when:

- A product is saved
- A product is changed
- A product is deleted

A red message appears inside the form when:

- A required field is empty
- Product Name is longer than 60 characters, or Category is longer than 30 characters
- Quantity is not a whole number, is negative, or is more than 1,000,000 pieces
- Price is not a normal number with up to 2 decimals (like 25 or 8.50), is negative, or is more than PHP 1,000,000.00
- Adding to a saved product would put its stock over 1,000,000 pieces
- An update would make the same product (same name, category, and price) as another one
- No product is selected before updating or deleting

Deleting a product still asks for confirmation in a pop-up first.

## Automatic Tests

`test_database.py` checks adding, adding to an existing product, updating, deleting, the totals, and the input checks. It uses a temporary database, so your saved products are not touched. Run it from the project folder:

```bash
python -m unittest test_database.py
```

It should end with `OK`.

## Suggested Manual Testing

1. Add a product.
2. Check if it appears in the product list.
3. Check if the totals at the top changed.
4. Try typing letters in Quantity.
5. Try a negative quantity.
6. Select a product and update it.
7. Delete a product.
8. Close and open the app again to check if saved products are still there.
