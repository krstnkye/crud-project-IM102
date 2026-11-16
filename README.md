# Product Inventory System

This is a simple IM102 project made with Python, Tkinter, and SQLite.

The app helps you keep a list of products. You can add a product, see the saved products, change product details, and delete products you no longer need.

Each person signs in with their own account first. Passwords are never saved as plain text, and every add, update, and delete is saved with the name of the user who did it.

There are two kinds of accounts:

- **Admin:** the first account made on a computer. An admin can do everything, including deleting products, opening Database Records, and using the **Admin Dashboard** to see all users and manage accounts.
- **Staff:** every account made after the first one. Staff can add and update products and use **My Dashboard**, but cannot delete products or open Database Records.

Every page (Inventory, My Dashboard, Admin Dashboard, and each user's profile) opens inside the same main window. Nothing opens in a new window except the Database Records viewer.

The five summary cards at the top of the app show:

- Total Inventory Value (quantity × unit price of all products)
- Total Products, with the total number of units
- Low Stock (products with less than 10 pieces)
- Out of Stock (products with 0 pieces)
- Database File (the size of `inventory.db`)

## What You Need

- Python 3.10 or newer
- Tkinter, which usually comes with Python
- No extra packages are needed

## Folder Structure

```text
crud-project-IM102/
|-- main.py              (main window, page switching, and product CRUD)
|-- profile_page.py      (My Dashboard and user profiles)
|-- admin_page.py        (Admin Dashboard)
|-- auth_screen.py       (Sign In and Create Account screen)
|-- auth.py              (password hashing, sign up, sign in)
|-- validation.py        (input checks shared by every form)
|-- database.py          (tables and SQL commands)
|-- database_viewer.py   (Database Records window)
|-- theme.py             (colors, fonts, dark/light mode)
|-- test_database.py     (automatic tests)
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

`inventory.db` is the saved database file. It is made automatically when the app runs and is not uploaded to GitHub, so each computer starts with no products and no accounts.

## Database Tables

| Table | What it keeps |
| --- | --- |
| `products` | product_id, product_name, category, quantity, unit_price, created_by and updated_by (link to `users`), created_at, updated_at |
| `users` | user_id, username (unique), full_name, password_hash, created_at, last_login, role (admin or staff), is_active |
| `activity_log` | log_id, user_id (links to `users`), action, details, created_at |

An older `inventory.db` from before accounts were added still works. The new tables and columns are added the next time the app starts, and the saved products are kept. If an older database has accounts but no admin yet, the oldest account becomes the admin.

## Sign In and Sign Up

The first time the app runs there are no accounts yet, so it opens on **Create Account**. After that it opens on **Sign In**.

- **Full name:** required, up to 60 characters.
- **Username:** 3 to 20 letters, numbers, dots, or underscores. It must not be used by another account (capital letters do not matter, so `Juan` and `juan` are the same).
- **Password:** at least 8 characters with at least one letter and one number, cannot be the same as the username, and must be typed twice the same way.
- **Show password** shows what you typed, and a warning appears when Caps Lock is on.
- After 5 wrong passwords in a row, sign in for that username is paused for 30 seconds.
- After **Create Account**, the app does not sign you in. It goes back to the Sign In screen with your new username filled in, and you sign in with the username and password you just made.
- An inactive account (deactivated by an admin) cannot sign in until an admin activates it again.
- **Sign Out** is at the bottom of the side menu. It goes back to the Sign In screen.

How passwords are kept safe: each password is mixed with a random 16-byte salt and run through PBKDF2-HMAC-SHA256 240,000 times (Python's built-in `hashlib`). Only the result is saved in `users.password_hash`. When you sign in, the same steps are done again and the two results are compared with `hmac.compare_digest`. Nobody, including the teacher opening the database, can read the original password.

## My Dashboard (every user)

Click **My Dashboard** in the side menu, or click your name at the bottom of it. It shows:

- Your name, username, role, user ID, when you joined, and when you last signed in
- How many products you added, updated or added stock to, and deleted
- Your own saved activity, newest first
- **Edit Profile** to change your full name, and **Change Password** (you must type your current password first)
- **Change Photo** to add or change your profile photo (a PNG or GIF picture under 2 MB, saved inside `inventory.db`), and **Remove Photo** to go back to your initials

## Admin Dashboard (admins only)

Click **Admin Dashboard** in the side menu. It shows:

- Total Users, Active Users, Changes Today, and Changes in the Last 7 Days
- The **Users** list with each user's role, status (Active or Inactive), number of changes, last update, and last sign in
- **All Activity**, which shows who did what, newest first. Click **Products Only** to hide sign-ins and sign-outs.

Double-click a user in the Users list (or click **View Profile**) to open their profile in the same window. There an admin can:

- **Set as Admin** or **Set as Staff** (the last admin cannot be set as staff)
- **Deactivate Account** or **Activate Account** (you cannot deactivate your own account)
- **Reset Password**, which shows a temporary password like `temp123456` to tell the person. They can change it in My Dashboard.

Every one of these actions is saved in the activity log with the admin's name. **‹ Back to Admin Dashboard** goes back to the Users list.

## Who Can Do What

| Action | Admin | Staff |
| --- | --- | --- |
| Add and update products | Yes | Yes |
| Delete products | Yes | No |
| My Dashboard, change own name and password | Yes | Yes |
| Admin Dashboard, see everyone's activity | Yes | No |
| Change roles, activate or deactivate accounts, reset passwords | Yes | No |
| Database Records window | Yes | No |

## How To Run

To get the project on another laptop, download it from GitHub first. Either click **Code → Download ZIP** on https://github.com/krstnkye/crud-project-IM102 and unzip it, or run:

```bash
git clone https://github.com/krstnkye/crud-project-IM102.git
```

Each laptop starts with an empty `inventory.db`. The first account made on that laptop becomes the Admin.

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
| Delete | Removes the selected product after asking first (admins only). |
| Clear Fields | Empties the form so you can type again. |
| New Product | Clears the form and puts the cursor in Product Name. |
| Database Records | (Admins only) Opens a window that shows the raw rows of the `products`, `users`, and `activity_log` tables, the database details, and quick queries. It updates by itself after every change. |
| Export CSV | In the Database Records window, saves the rows shown to a CSV file you can open in Excel. Password hashes are never exported. |
| My Dashboard | Shows your profile, your activity, and lets you change your name and password. |
| Admin Dashboard | (Admins only) Shows all users, everyone's activity, and account tools. |
| Sign Out | Signs out and goes back to the Sign In screen. |
| Light Mode / Dark Mode | Switches the app between the dark and light theme. |

Update and Delete can only be clicked after you select a product in the list.

## Helpful Extras

- **Dark and light mode:** click the theme button at the top (or press `Ctrl+L`). The app remembers your choice in `settings.json`, which stays on your own computer.
- **Category filter:** click a category chip above the table to show only that category.
- **Search:** type in the search box to filter products by ID, name, or category.
- **Sorting:** click a column heading to sort. Click it again to reverse the order.
- **Stock status:** products with less than 10 pieces are shown in amber, and products with 0 pieces in red.
- **Product details:** shows the selected product's stock, price, total value, status, a stock bar compared with the low stock line, and who changed it last.
- **Fonts:** the app uses Segoe UI, the normal Windows font. On Mac or Linux it uses a similar font that is already installed.
- **Activity log:** lists what was added, updated, or deleted and by whom. It is saved in the `activity_log` table, so the history is still there after the app is closed.
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
- A staff account tries to delete a product (only an admin can)

The Sign In and Create Account screen shows the same kind of red message when:

- A box is empty, or the username or password does not follow the rules above
- The username is already taken
- The two passwords do not match
- The username or password is wrong (it shows how many tries are left)

Deleting a product and signing out ask for confirmation in a pop-up first. If the database file is locked by another program, a pop-up explains the problem instead of the app closing, and nothing is lost.

## Automatic Tests

`test_database.py` has 30 tests. They check adding, adding to an existing product, updating, deleting, the totals, the product and sign up input checks, password hashing, sign up (without signing in), sign in, duplicate usernames, the wrong-password pause, the saved activity log, who changed each product, profile numbers, changing your name and password, the Admin and Staff roles, the admin tools (roles, deactivating accounts, password reset), and opening older databases. It uses a temporary database, so your saved products are not touched. Run it from the project folder:

```bash
python -m unittest test_database.py
```

It should end with `OK`.

## Suggested Manual Testing

1. Create the first account (it becomes the admin). Check that the app goes back to Sign In, then sign in with it.
2. Try signing in with a wrong password.
3. Add a product.
4. Check if it appears in the product list.
5. Check if the totals at the top changed.
6. Try typing letters in Quantity.
7. Try a negative quantity.
8. Select a product and update it.
9. Delete a product.
10. Open My Dashboard and check that your changes are listed.
11. Sign out and create a second account (it becomes staff). Sign in and check that Delete, Database Records, and Admin Dashboard are not available.
12. Sign in as the admin, open Admin Dashboard, open the staff profile, and try Reset Password and Deactivate Account.
13. Close and open the app again to check if saved products and the activity log are still there.
