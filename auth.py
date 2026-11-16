"""User accounts: password hashing, sign up, and sign in.

Passwords are never saved as plain text. Each password is turned into a hash
with PBKDF2-HMAC-SHA256 (built into Python's hashlib) and a random salt, and
only that hash is saved in the users table. To check a password at sign in,
the same steps are done again and the two hashes are compared.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

import database
from validation import ValidationError, validate_full_name, validate_password, validate_sign_in, validate_sign_up


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 240_000
SALT_BYTES = 16

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 30

# Wrong sign-in attempts per username: {username: (count, locked_until)}. Kept in memory only.
_failed_attempts = {}


@dataclass(frozen=True)
class User:
    user_id: int
    username: str
    full_name: str
    last_login: str | None = None
    role: str = "staff"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def role_name(self):
        return "Admin" if self.is_admin else "Staff"

    @property
    def initials(self):
        parts = self.full_name.split()
        letters = (parts[0][0] + parts[-1][0]) if len(parts) > 1 else self.full_name[:2]
        return letters.upper()


def hash_password(password, salt=None, iterations=ITERATIONS):
    """Return a text like "pbkdf2_sha256$240000$<salt>$<hash>" that is safe to save."""
    salt = salt or secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password, stored_hash):
    """Check a typed password against a saved hash without leaking timing information."""
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$")
        iterations = int(iterations)
    except (ValueError, AttributeError):
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hash_password(password, salt, iterations).split("$")[3]
    return hmac.compare_digest(candidate, expected)


# A real hash that matches no password; used so a wrong username takes as long as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def sign_up(full_name, username, password, confirm_password):
    """Create a new account. Returns the new User, or raises ValidationError.

    This does not sign the user in. They sign in afterwards with the username and password they chose.
    """
    full_name, username, password = validate_sign_up(full_name, username, password, confirm_password)
    # The very first account becomes the admin. Everyone who signs up after that is staff.
    role = "admin" if database.count_users() == 0 else "staff"
    user_id = database.create_user(username, full_name, hash_password(password), role)
    if user_id is None:
        raise ValidationError("That username is already taken. Please choose another one.", "username")
    database.add_activity(user_id, "SIGN UP", f"{'Admin' if role == 'admin' else 'Staff'} account created for {full_name}.")
    return User(user_id, username, full_name, role=role)


def seconds_locked(username):
    count, locked_until = _failed_attempts.get(username.strip().lower(), (0, 0.0))
    return max(0, int(locked_until - time.monotonic() + 0.999))


def sign_in(username, password):
    """Check the username and password. Returns the User, or raises ValidationError."""
    username, password = validate_sign_in(username, password)
    key = username.lower()

    wait = seconds_locked(username)
    if wait:
        raise ValidationError(f"Too many wrong attempts. Please wait {wait} seconds and try again.", "password")

    row = database.get_user_by_username(username)
    password_ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)

    if row is None or not password_ok:
        count = _failed_attempts.get(key, (0, 0.0))[0] + 1
        if count >= MAX_FAILED_ATTEMPTS:
            _failed_attempts[key] = (0, time.monotonic() + LOCKOUT_SECONDS)
            raise ValidationError(
                f"Too many wrong attempts. Sign in is paused for {LOCKOUT_SECONDS} seconds.", "password"
            )
        _failed_attempts[key] = (count, 0.0)
        left = MAX_FAILED_ATTEMPTS - count
        raise ValidationError(
            f"Wrong username or password. {left} attempt{'s' if left != 1 else ''} left.", "password"
        )

    _failed_attempts.pop(key, None)
    if not row["is_active"]:
        raise ValidationError("This account is inactive. Please ask an admin to activate it.", "username")

    # Upgrade old hashes to the current number of iterations.
    if row["password_hash"].split("$")[1] != str(ITERATIONS):
        database.set_password_hash(row["user_id"], hash_password(password))

    user = User(row["user_id"], row["username"], row["full_name"], row["last_login"], row["role"])
    database.record_login(user.user_id)
    database.add_activity(user.user_id, "SIGN IN", f"{user.full_name} signed in.")
    return user


def change_full_name(user, full_name):
    """Save a new display name. Returns the updated User, or raises ValidationError."""
    full_name = validate_full_name(full_name)
    if full_name == user.full_name:
        raise ValidationError("That is already your name.", "full_name")
    database.update_full_name(user.user_id, full_name)
    database.add_activity(user.user_id, "PROFILE", f"Changed name from {user.full_name} to {full_name}.")
    return User(user.user_id, user.username, full_name, user.last_login, user.role)


def change_password(user, current_password, new_password, confirm_password):
    """Change a password after checking the current one. Raises ValidationError if anything is wrong."""
    if not current_password:
        raise ValidationError("Please enter your current password.", "current")
    row = database.get_user_by_id(user.user_id)
    if row is None or not verify_password(current_password, row["password_hash"]):
        raise ValidationError("Your current password is not correct.", "current")
    try:
        validate_password(new_password)
    except ValidationError as error:
        raise ValidationError(error.message, "new") from None
    if new_password.lower() == user.username.lower():
        raise ValidationError("Password cannot be the same as the username.", "new")
    if new_password == current_password:
        raise ValidationError("The new password must be different from the current one.", "new")
    if confirm_password != new_password:
        raise ValidationError("The two new passwords do not match.", "confirm")
    database.set_password_hash(user.user_id, hash_password(new_password))
    database.add_activity(user.user_id, "PASSWORD", f"{user.full_name} changed their password.")


# ---------------------------------------------------------------- admin tools


def _require_admin(admin):
    if admin is None or not admin.is_admin:
        raise ValidationError("Only an admin can do this.")


def _target(user_id):
    row = database.get_user_by_id(user_id)
    if row is None:
        raise ValidationError("That account no longer exists.")
    return row


def admin_set_role(admin, user_id, role):
    """Make a user an admin or staff. The last active admin cannot be made staff."""
    _require_admin(admin)
    if role not in ("admin", "staff"):
        raise ValidationError("Unknown role.")
    row = _target(user_id)
    if row["role"] == role:
        return
    if role == "staff" and row["role"] == "admin" and database.count_active_admins() <= 1:
        raise ValidationError("There must always be at least one admin.")
    database.set_role(user_id, role)
    database.add_activity(admin.user_id, "ROLE", f"Made @{row['username']} {'an Admin' if role == 'admin' else 'Staff'}.")


def admin_set_active(admin, user_id, active):
    """Activate or deactivate an account. Admins cannot deactivate their own account."""
    _require_admin(admin)
    row = _target(user_id)
    if not active and user_id == admin.user_id:
        raise ValidationError("You cannot deactivate your own account.")
    if not active and row["role"] == "admin" and database.count_active_admins() <= 1:
        raise ValidationError("There must always be at least one active admin.")
    database.set_active(user_id, active)
    database.add_activity(admin.user_id, "ACCOUNT", f"{'Activated' if active else 'Deactivated'} the account of @{row['username']}.")


def admin_reset_password(admin, user_id):
    """Give a user a new temporary password and return it so the admin can pass it on."""
    _require_admin(admin)
    row = _target(user_id)
    temporary = f"temp{secrets.randbelow(10 ** 6):06d}"
    database.set_password_hash(user_id, hash_password(temporary))
    _failed_attempts.pop(row["username"].lower(), None)
    database.add_activity(admin.user_id, "PASSWORD", f"Reset the password of @{row['username']}.")
    return temporary


def sign_out(user):
    database.add_activity(user.user_id, "SIGN OUT", f"{user.full_name} signed out.")


MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
PHOTO_TYPES = {b"\x89PNG\r\n\x1a\n": "PNG", b"GIF87a": "GIF", b"GIF89a": "GIF"}


def change_photo(user, file_path):
    """Save a PNG or GIF picture (up to 2 MB) as the user's profile photo."""
    try:
        with open(file_path, "rb") as file:
            data = file.read(MAX_PHOTO_BYTES + 1)
    except OSError:
        raise ValidationError("That picture could not be opened. Please choose another one.")
    if not any(data.startswith(start) for start in PHOTO_TYPES):
        raise ValidationError("Please choose a PNG or GIF picture.")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValidationError("That picture is too big. Please choose one under 2 MB.")
    database.set_photo(user.user_id, data)
    database.add_activity(user.user_id, "PROFILE", "Changed profile photo.")


def remove_photo(user):
    """Remove the user's profile photo, so their initials show again."""
    database.set_photo(user.user_id, None)
    database.add_activity(user.user_id, "PROFILE", "Removed profile photo.")
