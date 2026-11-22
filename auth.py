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
ITERATIONS = 600_000
MIN_SAFE_ITERATIONS = 100_000
MAX_SAFE_ITERATIONS = 2_000_000
SALT_BYTES = 16

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 30

ROLE_PERMISSIONS = {
    "admin": frozenset({"edit_products", "manage_accounts", "delete_products", "view_database", "manage_profile"}),
    "staff": frozenset({"edit_products", "manage_profile"}),
}

# Kept as a compatibility shim for older callers; attempts are persisted in SQLite.
_failed_attempts = {}


@dataclass(frozen=True)
class User:
    user_id: int
    username: str
    full_name: str
    last_login: str | None = None
    role: str = "staff"
    must_change_password: bool = False

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
    if algorithm != ALGORITHM or not MIN_SAFE_ITERATIONS <= iterations <= MAX_SAFE_ITERATIONS:
        return False
    if len(salt) != SALT_BYTES * 2 or len(expected) != 64:
        return False
    try:
        bytes.fromhex(salt)
        bytes.fromhex(expected)
    except ValueError:
        return False
    candidate = hash_password(password, salt, iterations).split("$")[3]
    return hmac.compare_digest(candidate, expected)


# A real hash that matches no password; used so a wrong username takes as long as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def sign_up(full_name, username, password, confirm_password):
    """Create the initial administrator during first-time setup.

    Once any account exists, new accounts must be created by a signed-in administrator.
    """
    full_name, username, password = validate_sign_up(full_name, username, password, confirm_password)
    user_id = database.create_initial_admin(username, full_name, hash_password(password))
    if user_id == "already_initialized":
        raise ValidationError("Only a signed-in administrator can create another account.")
    if user_id is None:
        raise ValidationError("That username is already taken. Please choose another one.", "username")
    return User(user_id, username, full_name, role="admin")


def request_account(full_name, username, password, confirm_password, requested_role):
    """Submit a registration request that cannot sign in until an admin approves it."""
    if database.count_users() == 0:
        raise ValidationError("Set up the first administrator before requesting another account.")
    if requested_role not in ("admin", "staff"):
        raise ValidationError("Please choose Staff or Admin.", "role")
    full_name, username, password = validate_sign_up(full_name, username, password, confirm_password)
    result = database.submit_registration_request(
        username, full_name, hash_password(password), requested_role
    )
    if result == "username_exists":
        raise ValidationError("That username already belongs to an account.", "username")
    if result == "pending_exists":
        raise ValidationError("A request for that username is already waiting for approval.", "username")
    return result


def seconds_locked(username):
    _count, locked_until = database.get_login_state(username)
    return max(0, int(locked_until - time.time() + 0.999))


def sign_in(username, password, required_role=None):
    """Check credentials and, when supplied, require the selected login role."""
    if required_role not in (None, "admin", "staff"):
        raise ValueError("required_role must be 'admin', 'staff', or None")
    username, password = validate_sign_in(username, password)
    wait = seconds_locked(username)
    if wait:
        raise ValidationError(f"Too many wrong attempts. Please wait {wait} seconds and try again.", "password")

    row = database.get_user_by_username(username)
    password_ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)

    if row is None or not password_ok:
        left, locked_until = database.record_failed_login(
            username, MAX_FAILED_ATTEMPTS, LOCKOUT_SECONDS
        )
        if locked_until:
            raise ValidationError(
                f"Too many wrong attempts. Sign in is paused for {LOCKOUT_SECONDS} seconds.", "password"
            )
        raise ValidationError(
            f"Wrong username or password. {left} attempt{'s' if left != 1 else ''} left.", "password"
        )

    database.clear_login_attempts(username)
    if not row["is_active"]:
        raise ValidationError("This account is inactive. Please ask an admin to activate it.", "username")

    if required_role and row["role"] != required_role:
        if required_role == "admin":
            message = "Administrator account required. Staff members should use Staff Login."
        else:
            message = "Staff account required. Administrators should use Admin Login."
        raise ValidationError(message, "username")

    # Upgrade old hashes to the current number of iterations.
    if row["password_hash"].split("$")[1] != str(ITERATIONS):
        database.set_password_hash(row["user_id"], hash_password(password))

    user = User(
        row["user_id"], row["username"], row["full_name"], row["last_login"], row["role"],
        bool(row["must_change_password"]),
    )
    database.record_login(user.user_id)
    database.add_activity(user.user_id, "SIGN IN", f"{user.full_name} signed in.")
    return user


def change_full_name(user, full_name):
    """Save a new display name. Returns the updated User, or raises ValidationError."""
    require_permission(user, "manage_profile")
    full_name = validate_full_name(full_name)
    if full_name == user.full_name:
        raise ValidationError("That is already your name.", "full_name")
    database.update_full_name(user.user_id, full_name)
    database.add_activity(user.user_id, "PROFILE", f"Changed name from {user.full_name} to {full_name}.")
    return User(user.user_id, user.username, full_name, user.last_login, user.role)


def change_password(user, current_password, new_password, confirm_password):
    """Change a password after checking the current one. Raises ValidationError if anything is wrong."""
    require_permission(user, "manage_profile")
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
    if not database.change_own_password(user.user_id, hash_password(new_password)):
        raise ValidationError("Your account is no longer active. Please sign in again.")
    database.add_activity(user.user_id, "PASSWORD", f"{user.full_name} changed their password.")
    return User(user.user_id, user.username, user.full_name, user.last_login, user.role, False)


# ---------------------------------------------------------------- admin tools


def _require_admin(admin):
    return require_permission(admin, "manage_accounts")


def require_permission(user, permission):
    """Enforce RBAC using the account's current saved role and active status."""
    if permission not in ROLE_PERMISSIONS["admin"]:
        raise ValueError(f"Unknown permission: {permission}")
    row = database.get_user_by_id(user.user_id) if user is not None else None
    if row is None or not row["is_active"]:
        raise ValidationError("Your account is no longer active. Please sign in again.")
    if row["must_change_password"] and permission != "manage_profile":
        raise ValidationError("Change your temporary password in My Dashboard before continuing.")
    if permission not in ROLE_PERMISSIONS.get(row["role"], frozenset()):
        raise ValidationError("Only an active administrator can do this.")
    return row


def admin_create_user(admin, full_name, username, password, confirm_password, role):
    """Create an Admin or Staff account on behalf of a signed-in administrator."""
    _require_admin(admin)
    if role not in ("admin", "staff"):
        raise ValidationError("Please choose Staff or Admin.", "role")
    full_name, username, password = validate_sign_up(full_name, username, password, confirm_password)
    user_id = database.admin_create_user(admin.user_id, username, full_name, hash_password(password), role)
    if user_id == "forbidden":
        raise ValidationError("Only an active administrator can create accounts.")
    if user_id == "username_exists":
        raise ValidationError("That username is already taken. Please choose another one.", "username")
    return User(user_id, username, full_name, role=role)


def admin_approve_registration(admin, request_id, role):
    """Approve a pending request with the administrator's selected final role."""
    _require_admin(admin)
    if role not in ("admin", "staff"):
        raise ValidationError("Please choose Staff or Admin.", "role")
    result = database.approve_registration_request(request_id, admin.user_id, role)
    if result == "forbidden":
        raise ValidationError("Only an active administrator can approve account requests.")
    if result is None:
        raise ValidationError("That registration request is no longer pending.")
    if result == "username_exists":
        raise ValidationError("That username already belongs to an account.")
    user_id, username, full_name = result
    return User(user_id, username, full_name, role=role)


def admin_reject_registration(admin, request_id):
    """Reject a pending request and discard its saved password hash."""
    _require_admin(admin)
    result = database.reject_registration_request(request_id, admin.user_id)
    if result == "forbidden":
        raise ValidationError("Only an active administrator can reject account requests.")
    if result is None:
        raise ValidationError("That registration request is no longer pending.")
    return result


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
    result = database.admin_set_role(admin.user_id, user_id, role)
    if result == "forbidden":
        raise ValidationError("Only an active administrator can change roles.")
    if result == "missing":
        raise ValidationError("That account no longer exists.")
    if result == "last_admin":
        raise ValidationError("There must always be at least one admin.")


def admin_set_active(admin, user_id, active):
    """Activate or deactivate an account. Admins cannot deactivate their own account."""
    _require_admin(admin)
    result = database.admin_set_active(admin.user_id, user_id, active)
    if result == "forbidden":
        raise ValidationError("Only an active administrator can change account status.")
    if result == "missing":
        raise ValidationError("That account no longer exists.")
    if result == "self":
        raise ValidationError("You cannot deactivate your own account.")
    if result == "last_admin":
        raise ValidationError("There must always be at least one active admin.")


def admin_reset_password(admin, user_id):
    """Give a user a new temporary password and return it so the admin can pass it on."""
    _require_admin(admin)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    temporary = "Tmp!" + "".join(secrets.choice(alphabet) for _ in range(12))
    result = database.admin_reset_password(admin.user_id, user_id, hash_password(temporary))
    if result == "forbidden":
        raise ValidationError("Only an active administrator can reset passwords.")
    if result == "missing":
        raise ValidationError("That account no longer exists.")
    return temporary


def sign_out(user):
    database.add_activity(user.user_id, "SIGN OUT", f"{user.full_name} signed out.")


MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
PHOTO_TYPES = {b"\x89PNG\r\n\x1a\n": "PNG", b"GIF87a": "GIF", b"GIF89a": "GIF"}


def change_photo(user, file_path):
    """Save a PNG or GIF picture (up to 2 MB) as the user's profile photo."""
    require_permission(user, "manage_profile")
    try:
        with open(file_path, "rb") as file:
            data = file.read(MAX_PHOTO_BYTES + 1)
    except OSError:
        raise ValidationError("That picture could not be opened. Please choose another one.")
    if not any(data.startswith(start) for start in PHOTO_TYPES):
        raise ValidationError("Please choose a PNG or GIF picture.")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValidationError("That picture is too big. Please choose one under 2 MB.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        valid = len(data) >= 33 and data[12:16] == b"IHDR" and data.endswith(b"IEND\xaeB`\x82")
        width = int.from_bytes(data[16:20], "big") if valid else 0
        height = int.from_bytes(data[20:24], "big") if valid else 0
    else:
        valid = len(data) >= 14 and data.endswith(b";")
        width = int.from_bytes(data[6:8], "little") if valid else 0
        height = int.from_bytes(data[8:10], "little") if valid else 0
    if not valid or not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValidationError("That picture is damaged or has unsafe dimensions.")
    database.set_photo(user.user_id, data)
    database.add_activity(user.user_id, "PROFILE", "Changed profile photo.")


def remove_photo(user):
    """Remove the user's profile photo, so their initials show again."""
    require_permission(user, "manage_profile")
    database.set_photo(user.user_id, None)
    database.add_activity(user.user_id, "PROFILE", "Removed profile photo.")
