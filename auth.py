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
from validation import ValidationError, validate_sign_in, validate_sign_up


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
    """Create a new account. Returns the new User, or raises ValidationError."""
    full_name, username, password = validate_sign_up(full_name, username, password, confirm_password)
    user_id = database.create_user(username, full_name, hash_password(password))
    if user_id is None:
        raise ValidationError("That username is already taken. Please choose another one.", "username")
    database.record_login(user_id)
    database.add_activity(user_id, "SIGN UP", f"Account created for {full_name}.")
    return User(user_id, username, full_name)


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

    # Upgrade old hashes to the current number of iterations.
    if row["password_hash"].split("$")[1] != str(ITERATIONS):
        database.set_password_hash(row["user_id"], hash_password(password))

    user = User(row["user_id"], row["username"], row["full_name"], row["last_login"])
    database.record_login(user.user_id)
    database.add_activity(user.user_id, "SIGN IN", f"{user.full_name} signed in.")
    return user


def sign_out(user):
    database.add_activity(user.user_id, "SIGN OUT", f"{user.full_name} signed out.")
