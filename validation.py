"""Input checks shared by the product form and the sign in / sign up screen.

Every check returns a plain message that can be shown to the user, so the
screens stay simple and the rules can be tested without opening a window.
"""

import re

import database


MAX_NAME_LENGTH = 60
MAX_CATEGORY_LENGTH = 30

QUANTITY_PATTERN = re.compile(r"-?\d+", re.ASCII)
PRICE_PATTERN = re.compile(r"-?(\d+(\.\d{1,2})?|\.\d{1,2})", re.ASCII)

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.]+", re.ASCII)
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_FULL_NAME_LENGTH = 60


class ValidationError(ValueError):
    """A problem with what the user typed. `field` names the box that needs fixing."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def parse_quantity(text):
    """Return the quantity as a whole number, or None if it is not a plain whole number."""
    text = text.strip()
    return int(text) if QUANTITY_PATTERN.fullmatch(text) else None


def parse_price(text):
    """Return the price as a number with at most 2 decimal places, or None if it is not valid."""
    text = text.strip()
    return float(text) if PRICE_PATTERN.fullmatch(text) else None


def clean_text(text):
    """Remove spaces at both ends and squeeze repeated spaces inside."""
    return " ".join(text.split())


def validate_product(product_name, category, quantity_text, price_text):
    """Check the product form. Returns (name, category, quantity, price) or raises ValidationError."""
    product_name = clean_text(product_name)
    category = clean_text(category)

    if not product_name:
        raise ValidationError("Please enter a product name.", "name")
    if len(product_name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Product name must be {MAX_NAME_LENGTH} characters or less.", "name")

    if not category:
        raise ValidationError("Please enter a category.", "category")
    if len(category) > MAX_CATEGORY_LENGTH:
        raise ValidationError(f"Category must be {MAX_CATEGORY_LENGTH} characters or less.", "category")

    if not quantity_text.strip():
        raise ValidationError("Please enter a quantity.", "quantity")
    quantity = parse_quantity(quantity_text)
    if quantity is None:
        raise ValidationError("Quantity must be a whole number.", "quantity")
    if quantity < 0:
        raise ValidationError("Quantity cannot be negative.", "quantity")
    if quantity > database.MAX_QUANTITY:
        raise ValidationError(f"Quantity cannot be more than {database.MAX_QUANTITY:,} pcs.", "quantity")

    if not price_text.strip():
        raise ValidationError("Please enter a unit price.", "price")
    unit_price = parse_price(price_text)
    if unit_price is None or unit_price < 0:
        raise ValidationError("Please enter a valid price, like 25 or 8.50.", "price")
    if unit_price > database.MAX_PRICE:
        raise ValidationError(f"Price cannot be more than PHP {database.MAX_PRICE:,.2f}.", "price")

    return product_name, category, quantity, unit_price


def validate_username(username):
    username = username.strip()
    if not username:
        raise ValidationError("Please enter a username.", "username")
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise ValidationError(
            f"Username must be {MIN_USERNAME_LENGTH} to {MAX_USERNAME_LENGTH} characters long.", "username"
        )
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValidationError("Username can only use letters, numbers, dots (.) and underscores (_).", "username")
    return username


def validate_password(password):
    if not password:
        raise ValidationError("Please enter a password.", "password")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.", "password")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be {MAX_PASSWORD_LENGTH} characters or less.", "password")
    if password != password.strip():
        raise ValidationError("Password cannot start or end with a space.", "password")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise ValidationError("Password must have at least one letter and one number.", "password")
    return password


def validate_full_name(full_name):
    full_name = clean_text(full_name)
    if not full_name:
        raise ValidationError("Please enter your full name.", "full_name")
    if len(full_name) < 2:
        raise ValidationError("Full name is too short.", "full_name")
    if len(full_name) > MAX_FULL_NAME_LENGTH:
        raise ValidationError(f"Full name must be {MAX_FULL_NAME_LENGTH} characters or less.", "full_name")
    return full_name


def validate_sign_up(full_name, username, password, confirm_password):
    """Check the Create Account form. Returns (full_name, username, password) or raises ValidationError."""
    full_name = validate_full_name(full_name)
    username = validate_username(username)
    password = validate_password(password)
    if password.lower() == username.lower():
        raise ValidationError("Password cannot be the same as the username.", "password")
    if confirm_password != password:
        raise ValidationError("The two passwords do not match.", "confirm")
    return full_name, username, password


def validate_sign_in(username, password):
    """Only checks that both boxes are filled in; the real check is done against the database."""
    username = username.strip()
    if not username:
        raise ValidationError("Please enter your username.", "username")
    if not password:
        raise ValidationError("Please enter your password.", "password")
    return username, password
