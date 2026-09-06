"""CouponManager - JSON file-backed coupon management with in-memory caching."""

import json
import logging
import secrets
import string
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("pdn_admin")

_MAX_CODE_GENERATION_ATTEMPTS = 1000
_MAX_COUPON_NAME_LENGTH = 100


def generate_coupon_code(existing_codes: set) -> str:
    """Generate a unique 8-character alphanumeric code [A-Z0-9].

    Uses cryptographically secure randomness to make codes unguessable.
    Raises RuntimeError if unable to generate a unique code after max attempts.
    """
    charset = string.ascii_uppercase + string.digits
    for _ in range(_MAX_CODE_GENERATION_ATTEMPTS):
        code = ''.join(secrets.choice(charset) for _ in range(8))
        if code not in existing_codes:
            return code
    raise RuntimeError("Unable to generate unique coupon code after max attempts")


def validate_custom_code(code: str) -> Tuple[bool, str]:
    """Validate a custom code: 4-20 alphanumeric characters.

    Returns (is_valid, error_message).
    """
    if not isinstance(code, str):
        return False, "Code must be a string"
    if len(code) < 4 or len(code) > 20:
        return False, "Code must be 4-20 alphanumeric characters"
    if not code.isalnum():
        return False, "Code must be 4-20 alphanumeric characters"
    return True, ""


class CouponManager:
    """Manages coupon data with JSON file persistence and in-memory caching."""

    def __init__(self, json_path: Optional[Path] = None):
        if json_path:
            self._json_path = json_path
        else:
            # Use persistent disk path (SAVED_RESULTS_DIR) in production,
            # fall back to app/data/coupons.json for local development
            import os
            saved_results_dir = os.getenv('SAVED_RESULTS_DIR')
            if saved_results_dir:
                self._json_path = Path(saved_results_dir) / "coupons.json"
            else:
                self._json_path = Path(__file__).parent.parent / "data" / "coupons.json"
        self._coupons: dict = {}
        self._lock = threading.Lock()
        # No lock needed here — instance isn't shared yet during __init__
        self._load_initial_data()

    # --- Core data operations ---

    def _load_initial_data(self) -> None:
        """Load coupons from JSON file on startup. No lock needed (called from __init__ only)."""
        if self._json_path.exists():
            try:
                data = json.loads(self._json_path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    self._coupons = data
                    return
            except (json.JSONDecodeError, OSError):
                pass
        # Initialize with empty data
        self._coupons = {}
        self._save_to_file()

    def _save_to_file(self) -> None:
        """Persist current in-memory coupons to JSON file atomically."""
        tmp_path = self._json_path.with_suffix('.tmp')
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(self._coupons, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        tmp_path.replace(self._json_path)

    def get_status(self, coupon: dict) -> str:
        """Derive status from usage_count and max_usage.

        Returns 'active' if usage_count < max_usage, 'full' otherwise.
        """
        usage_count = coupon.get("usage_count", 0)
        max_usage = coupon.get("max_usage", 0)
        if usage_count < max_usage:
            return "active"
        return "full"

    # --- CRUD operations ---

    def create_coupon(self, name: str, max_usage: int, code: Optional[str] = None) -> dict:
        """Create a new coupon. Auto-generates code if not provided.

        Returns a copy of the created coupon dict.
        Raises ValueError if code is duplicate, invalid, or name too long.
        """
        with self._lock:
            if not name or len(name) > _MAX_COUPON_NAME_LENGTH:
                raise ValueError(f"Name must be 1-{_MAX_COUPON_NAME_LENGTH} characters")

            if not isinstance(max_usage, int) or max_usage < 1:
                raise ValueError("Max usage must be at least 1")

            if code is not None:
                is_valid, error_msg = validate_custom_code(code)
                if not is_valid:
                    raise ValueError(error_msg)
                if code in self._coupons:
                    raise ValueError("Coupon code already exists")
            else:
                code = generate_coupon_code(set(self._coupons.keys()))

            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            coupon = {
                "name": name,
                "code": code,
                "max_usage": max_usage,
                "usage_count": 0,
                "used_by": [],
                "created_at": now,
                "updated_at": now,
            }
            self._coupons[code] = coupon
            self._save_to_file()
            return dict(coupon)

    def get_coupon(self, code: str) -> Optional[dict]:
        """Get a single coupon by code. Returns a copy, or None if not found."""
        with self._lock:
            coupon = self._coupons.get(code)
            return dict(coupon) if coupon else None

    def get_all_coupons(self) -> list:
        """Return all coupons as a list of dicts with status added."""
        with self._lock:
            result = []
            for coupon in self._coupons.values():
                coupon_with_status = dict(coupon)
                coupon_with_status["status"] = self.get_status(coupon)
                result.append(coupon_with_status)
            return result

    def update_coupon(self, coupon_code: str, **updates) -> dict:
        """Update coupon fields (name, max_usage). Code is immutable.

        Returns a copy of the updated coupon.
        Raises KeyError if not found, ValueError if invalid updates.
        """
        with self._lock:
            if coupon_code not in self._coupons:
                raise KeyError(f"Coupon not found: {coupon_code}")

            # Code is immutable - reject any attempt to change it
            if "code" in updates:
                raise ValueError("Coupon code cannot be modified")

            allowed_fields = {"name", "max_usage"}
            for key in updates:
                if key not in allowed_fields:
                    raise ValueError(f"Cannot update field: {key}")

            coupon = self._coupons[coupon_code]

            # Validate name length if being updated
            if "name" in updates and len(updates["name"]) > _MAX_COUPON_NAME_LENGTH:
                raise ValueError(f"Name must be 1-{_MAX_COUPON_NAME_LENGTH} characters")

            # Prevent setting max_usage below current usage_count
            if "max_usage" in updates:
                if not isinstance(updates["max_usage"], int) or updates["max_usage"] < 1:
                    raise ValueError("Max usage must be at least 1")
                if updates["max_usage"] < coupon["usage_count"]:
                    raise ValueError(f"Max usage cannot be less than current usage ({coupon['usage_count']})")

            for key, value in updates.items():
                coupon[key] = value

            coupon["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_to_file()
            return dict(coupon)

    def delete_coupon(self, code: str) -> None:
        """Delete a coupon by code. Raises KeyError if not found."""
        with self._lock:
            if code not in self._coupons:
                raise KeyError(f"Coupon not found: {code}")
            del self._coupons[code]
            self._save_to_file()

    def validate_coupon(self, code: str) -> Tuple[bool, str]:
        """Check if a coupon code is valid and has remaining uses (read-only).

        Returns (is_valid, message). Does not modify any state.
        """
        with self._lock:
            if code not in self._coupons:
                return False, "Invalid coupon code"

            coupon = self._coupons[code]
            if coupon["usage_count"] >= coupon["max_usage"]:
                return False, "Coupon has reached its usage limit"

            return True, "Valid"

    def redeem_coupon(self, code: str, email: str) -> dict:
        """Record a coupon redemption. Increments usage_count, adds email to used_by.

        Returns a copy of the updated coupon.
        Raises ValueError if coupon is full or not found.
        If the email already redeemed this coupon, returns without incrementing.
        """
        with self._lock:
            if code not in self._coupons:
                raise ValueError(f"Coupon not found: {code}")

            coupon = self._coupons[code]

            # Already redeemed by this email — allow re-login without counting
            if email in coupon["used_by"]:
                return dict(coupon)

            if coupon["usage_count"] >= coupon["max_usage"]:
                raise ValueError("Coupon has reached its usage limit")

            coupon["usage_count"] += 1
            coupon["used_by"].append(email)
            coupon["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_to_file()
            return dict(coupon)

    def validate_and_redeem(self, code: str, email: str) -> Tuple[bool, str, Optional[dict]]:
        """Atomically validate and redeem a coupon in a single lock acquisition.

        Returns (success, message, coupon_copy_or_none).
        Prevents race conditions between validate and redeem.
        If the email already redeemed this coupon, allows login without incrementing usage.
        """
        with self._lock:
            if code not in self._coupons:
                return False, "Invalid coupon code", None

            coupon = self._coupons[code]

            # If user already redeemed, allow re-login without counting again
            if email in coupon["used_by"]:
                return True, "Valid", dict(coupon)

            if coupon["usage_count"] >= coupon["max_usage"]:
                return False, "Coupon has reached its usage limit", None

            coupon["usage_count"] += 1
            coupon["used_by"].append(email)
            coupon["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_to_file()
            return True, "Valid", dict(coupon)

    def to_response(self, coupon: dict) -> dict:
        """Convert a coupon dict to an API response dict with status included."""
        result = dict(coupon)
        result["status"] = self.get_status(coupon)
        return result


# Module-level singleton with thread-safe initialization
_coupon_manager: Optional[CouponManager] = None
_coupon_manager_lock = threading.Lock()


def get_coupon_manager() -> CouponManager:
    """Get or create the singleton CouponManager instance (thread-safe)."""
    global _coupon_manager
    if _coupon_manager is None:
        with _coupon_manager_lock:
            if _coupon_manager is None:
                _coupon_manager = CouponManager()
    return _coupon_manager
