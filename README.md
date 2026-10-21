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

The app shows simple pop-up messages when:

- A product is saved
- A product is changed
- A product is deleted
- A required field is empty
- Quantity or price has an invalid value
- No product is selected before updating or deleting

## Suggested Testing

1. Add a product.
2. Check if it appears in the product list.
3. Check if the totals at the top changed.
4. Try typing letters in Quantity.
5. Try a negative quantity.
6. Select a product and update it.
7. Delete a product.
8. Close and open the app again to check if saved products are still there.
