"""Property-based tests for CouponManager code generation and validation.

**Validates: Requirements 1.1, 1.4, 6.1, 6.2, 6.3, 2.2, 7.1, 7.2, 7.3**

Uses Hypothesis for property-based testing with @settings(max_examples=100).
"""

import re
import string
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.pdn_admin.coupon_manager import (
    generate_coupon_code,
    validate_custom_code,
    CouponManager,
)


# --- Strategies ---

# Strategy for sets of existing coupon codes (valid 8-char [A-Z0-9] codes)
valid_code_charset = string.ascii_uppercase + string.digits
existing_codes_strategy = st.frozensets(
    st.text(alphabet=valid_code_charset, min_size=8, max_size=8),
    min_size=0,
    max_size=50,
)

# Strategy for arbitrary strings to test custom code validation
arbitrary_string_strategy = st.text(min_size=0, max_size=30)

# Strategy for valid custom codes (4-20 alphanumeric chars)
alphanumeric_charset = string.ascii_letters + string.digits
valid_custom_code_strategy = st.text(
    alphabet=alphanumeric_charset, min_size=4, max_size=20
)

# Strategy for usage_count and max_usage values
usage_count_strategy = st.integers(min_value=0, max_value=10000)
max_usage_strategy = st.integers(min_value=0, max_value=10000)


# --- Property 1: Code generation format ---

class TestProperty1CodeGenerationFormat:
    """Property 1: Code generation format.

    *For any* generated coupon code, it SHALL consist of exactly 8 characters
    drawn exclusively from the character set [A-Z, 0-9].

    **Validates: Requirements 1.1, 6.1**
    """

    @given(existing_codes=existing_codes_strategy)
    @settings(max_examples=100)
    def test_generated_code_is_8_chars_from_az09(self, existing_codes):
        """For any generated code, verify 8 chars from [A-Z0-9]."""
        code = generate_coupon_code(set(existing_codes))

        # Exactly 8 characters
        assert len(code) == 8, f"Expected 8 chars, got {len(code)}: '{code}'"

        # All characters from [A-Z0-9]
        valid_pattern = re.compile(r'^[A-Z0-9]{8}$')
        assert valid_pattern.match(code), (
            f"Code '{code}' contains characters outside [A-Z0-9]"
        )


# --- Property 2: Code uniqueness ---

class TestProperty2CodeUniqueness:
    """Property 2: Code uniqueness.

    *For any* set of existing coupon codes and a newly generated code,
    the new code SHALL NOT be equal to any existing code in the set.

    **Validates: Requirements 1.4, 6.2**
    """

    @given(existing_codes=existing_codes_strategy)
    @settings(max_examples=100)
    def test_generated_code_not_in_existing_codes(self, existing_codes):
        """For any set of existing codes, new code is not a duplicate."""
        code = generate_coupon_code(set(existing_codes))

        assert code not in existing_codes, (
            f"Generated code '{code}' is a duplicate of an existing code"
        )


# --- Property 5: Custom code validation ---

class TestProperty5CustomCodeValidation:
    """Property 5: Custom code validation.

    *For any* string, it SHALL be accepted as a valid custom coupon code
    if and only if it is between 4 and 20 characters in length and consists
    entirely of alphanumeric characters [A-Z, a-z, 0-9].

    **Validates: Requirements 6.3**
    """

    @given(code=valid_custom_code_strategy)
    @settings(max_examples=100)
    def test_valid_codes_are_accepted(self, code):
        """Valid codes (4-20 alphanumeric chars) are accepted."""
        is_valid, error_msg = validate_custom_code(code)

        assert is_valid is True, (
            f"Valid code '{code}' was rejected with: '{error_msg}'"
        )
        assert error_msg == ""

    @given(code=arbitrary_string_strategy)
    @settings(max_examples=100)
    def test_accept_iff_4_to_20_alphanumeric(self, code):
        """Accept iff 4-20 alphanumeric chars."""
        is_valid, error_msg = validate_custom_code(code)

        # Determine expected validity
        expected_valid = (
            len(code) >= 4
            and len(code) <= 20
            and code.isalnum()
        )

        assert is_valid == expected_valid, (
            f"Code '{code}' (len={len(code)}, alnum={code.isalnum() if code else False}): "
            f"expected valid={expected_valid}, got valid={is_valid}"
        )


# --- Property 4: Status derivation ---

class TestProperty4StatusDerivation:
    """Property 4: Status derivation.

    *For any* coupon with usage_count and max_usage values, the derived status
    SHALL be "active" if usage_count < max_usage, and "full" if
    usage_count >= max_usage.

    **Validates: Requirements 2.2, 7.1, 7.2, 7.3**
    """

    @given(
        usage_count=usage_count_strategy,
        max_usage=max_usage_strategy,
    )
    @settings(max_examples=100)
    def test_status_derivation_correctness(self, usage_count, max_usage):
        """Correct status from usage_count and max_usage."""
        coupon = {"usage_count": usage_count, "max_usage": max_usage}

        manager = CouponManager.__new__(CouponManager)
        status = manager.get_status(coupon)

        if usage_count < max_usage:
            assert status == "active", (
                f"Expected 'active' for usage={usage_count} < max={max_usage}, got '{status}'"
            )
        else:
            assert status == "full", (
                f"Expected 'full' for usage={usage_count} >= max={max_usage}, got '{status}'"
            )


# --- Strategies for CRUD property tests ---

# Strategy for coupon names (non-empty strings)
coupon_name_strategy = st.text(min_size=1, max_size=50)

# Strategy for max_usage values (valid: >= 1)
valid_max_usage_strategy = st.integers(min_value=1, max_value=10000)

# Strategy for optional custom codes (either None or a valid 4-20 alphanumeric string)
optional_custom_code_strategy = st.one_of(
    st.none(),
    st.text(alphabet=alphanumeric_charset, min_size=4, max_size=20),
)


def _make_manager():
    """Create a CouponManager with a fresh temporary JSON file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    tmp.write("{}")
    tmp.close()
    return CouponManager(json_path=Path(tmp.name))


# --- Property 3: Coupon creation round-trip ---

class TestProperty3CouponCreationRoundTrip:
    """Property 3: Coupon creation round-trip.

    *For any* valid coupon creation input (name, max_usage, optional custom code),
    after creation the stored coupon SHALL contain the correct name, code
    (custom or generated), max_usage, usage_count of 0, an empty used_by list,
    and a creation timestamp.

    **Validates: Requirements 1.2, 1.3, 1.5**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        custom_code=optional_custom_code_strategy,
    )
    @settings(max_examples=100)
    def test_creation_stores_all_fields_correctly(self, name, max_usage, custom_code):
        """After create_coupon, the stored coupon has correct fields."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage, code=custom_code)

        # Verify name
        assert coupon["name"] == name

        # Verify code
        if custom_code is not None:
            assert coupon["code"] == custom_code
        else:
            # Auto-generated: 8 chars [A-Z0-9]
            assert len(coupon["code"]) == 8
            assert re.match(r'^[A-Z0-9]{8}$', coupon["code"])

        # Verify max_usage
        assert coupon["max_usage"] == max_usage

        # Verify initial usage_count is 0
        assert coupon["usage_count"] == 0

        # Verify empty used_by list
        assert coupon["used_by"] == []

        # Verify timestamps exist
        assert "created_at" in coupon
        assert "updated_at" in coupon
        assert coupon["created_at"] == coupon["updated_at"]

        # Verify round-trip: get_coupon returns the same data
        retrieved = manager.get_coupon(coupon["code"])
        assert retrieved is not None
        assert retrieved["name"] == name
        assert retrieved["max_usage"] == max_usage
        assert retrieved["usage_count"] == 0
        assert retrieved["used_by"] == []


# --- Property 6: Code immutability ---

class TestProperty6CodeImmutability:
    """Property 6: Code immutability.

    *For any* existing coupon and any update operation, the coupon's code field
    SHALL remain unchanged after the update completes.

    **Validates: Requirements 3.3**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        new_name=coupon_name_strategy,
        new_max_usage=valid_max_usage_strategy,
    )
    @settings(max_examples=100)
    def test_code_unchanged_after_update(self, name, max_usage, new_name, new_max_usage):
        """After update_coupon, the coupon's code field is unchanged."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        original_code = coupon["code"]

        # Update name
        updated = manager.update_coupon(original_code, name=new_name)
        assert updated["code"] == original_code

        # Update max_usage
        updated = manager.update_coupon(original_code, max_usage=new_max_usage)
        assert updated["code"] == original_code

        # Update both
        updated = manager.update_coupon(original_code, name=new_name, max_usage=new_max_usage)
        assert updated["code"] == original_code

        # Verify via get_coupon
        retrieved = manager.get_coupon(original_code)
        assert retrieved["code"] == original_code


# --- Property 7: Update persistence ---

class TestProperty7UpdatePersistence:
    """Property 7: Update persistence.

    *For any* existing coupon and valid update values for name or max_usage,
    after the update operation the stored coupon SHALL reflect the new values
    for the updated fields while preserving all other fields.

    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        new_name=coupon_name_strategy,
        new_max_usage=valid_max_usage_strategy,
    )
    @settings(max_examples=100)
    def test_updated_fields_reflect_new_values(self, name, max_usage, new_name, new_max_usage):
        """After update_coupon, updated fields reflect new values."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        original_code = coupon["code"]
        original_usage_count = coupon["usage_count"]
        original_used_by = coupon["used_by"]
        original_created_at = coupon["created_at"]

        # Update name only
        updated = manager.update_coupon(original_code, name=new_name)
        assert updated["name"] == new_name
        assert updated["max_usage"] == max_usage  # preserved
        assert updated["usage_count"] == original_usage_count  # preserved
        assert updated["used_by"] == original_used_by  # preserved
        assert updated["created_at"] == original_created_at  # preserved

        # Update max_usage only
        updated = manager.update_coupon(original_code, max_usage=new_max_usage)
        assert updated["max_usage"] == new_max_usage
        assert updated["name"] == new_name  # preserved from previous update
        assert updated["usage_count"] == original_usage_count  # preserved
        assert updated["used_by"] == original_used_by  # preserved
        assert updated["created_at"] == original_created_at  # preserved

        # Verify persistence via get_coupon
        retrieved = manager.get_coupon(original_code)
        assert retrieved["name"] == new_name
        assert retrieved["max_usage"] == new_max_usage


# --- Property 8: Deletion removes coupon ---

class TestProperty8DeletionRemovesCoupon:
    """Property 8: Deletion removes coupon.

    *For any* existing coupon, after deletion the coupon SHALL NOT be
    retrievable from the data store.

    **Validates: Requirements 4.1**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
    )
    @settings(max_examples=100)
    def test_coupon_not_retrievable_after_delete(self, name, max_usage):
        """After delete_coupon, get_coupon returns None."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Verify coupon exists before deletion
        assert manager.get_coupon(code) is not None

        # Delete the coupon
        manager.delete_coupon(code)

        # Verify coupon is no longer retrievable
        assert manager.get_coupon(code) is None

        # Verify it's not in the list of all coupons
        all_coupons = manager.get_all_coupons()
        all_codes = [c["code"] for c in all_coupons]
        assert code not in all_codes


# --- Strategies for validation and redemption property tests ---

# Strategy for email addresses
email_strategy = st.emails()

# Strategy for coupon codes that may or may not exist (mix of valid and random)
random_code_strategy = st.text(
    alphabet=valid_code_charset, min_size=4, max_size=20
)


# --- Property 9: Coupon validation correctness ---

class TestProperty9CouponValidationCorrectness:
    """Property 9: Coupon validation correctness.

    *For any* coupon code submission, access SHALL be granted if and only if
    the code exists in the data store AND the coupon's usage_count is strictly
    less than its max_usage.

    **Validates: Requirements 5.1, 5.2, 5.3**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
    )
    @settings(max_examples=100)
    def test_valid_coupon_grants_access(self, name, max_usage):
        """A coupon that exists and is not full validates successfully."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Coupon exists and usage_count (0) < max_usage (>= 1), so should be valid
        is_valid, message = manager.validate_coupon(code)

        assert is_valid is True, (
            f"Expected valid=True for existing coupon with usage=0 < max={max_usage}, "
            f"got valid={is_valid}, message='{message}'"
        )

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        nonexistent_code=random_code_strategy,
    )
    @settings(max_examples=100)
    def test_nonexistent_code_denies_access(self, name, max_usage, nonexistent_code):
        """A code that does not exist in the data store is rejected."""
        manager = _make_manager()

        # Create a coupon so the store is not empty
        coupon = manager.create_coupon(name=name, max_usage=max_usage)

        # Ensure the nonexistent_code is actually not in the store
        assume(nonexistent_code != coupon["code"])

        is_valid, message = manager.validate_coupon(nonexistent_code)

        assert is_valid is False, (
            f"Expected valid=False for nonexistent code '{nonexistent_code}', "
            f"got valid={is_valid}"
        )

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_full_coupon_denies_access(self, name, max_usage):
        """A coupon that has reached max_usage is rejected."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Fill the coupon to capacity
        for i in range(max_usage):
            manager.redeem_coupon(code, f"user{i}@example.com")

        # Now validate - should be rejected
        is_valid, message = manager.validate_coupon(code)

        assert is_valid is False, (
            f"Expected valid=False for full coupon (usage={max_usage}/{max_usage}), "
            f"got valid={is_valid}"
        )

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=2, max_value=20),
        redemptions=st.integers(min_value=1, max_value=19),
    )
    @settings(max_examples=100)
    def test_validation_iff_exists_and_not_full(self, name, max_usage, redemptions):
        """Access granted iff code exists AND usage_count < max_usage."""
        assume(redemptions < max_usage)

        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Partially redeem
        for i in range(redemptions):
            manager.redeem_coupon(code, f"user{i}@example.com")

        # Still has capacity: should be valid
        is_valid, message = manager.validate_coupon(code)
        assert is_valid is True, (
            f"Expected valid=True for coupon with usage={redemptions} < max={max_usage}, "
            f"got valid={is_valid}"
        )


# --- Property 10: Redemption increments usage ---

class TestProperty10RedemptionIncrementsUsage:
    """Property 10: Redemption increments usage.

    *For any* valid coupon and any email address, after successful redemption
    the coupon's usage_count SHALL equal the previous usage_count plus one,
    and the email SHALL appear in the coupon's used_by list.

    **Validates: Requirements 5.4**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        email=email_strategy,
    )
    @settings(max_examples=100)
    def test_redemption_increments_usage_count(self, name, max_usage, email):
        """After redeem_coupon, usage_count equals previous + 1."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Get usage_count before redemption
        before = manager.get_coupon(code)
        usage_before = before["usage_count"]

        # Redeem
        manager.redeem_coupon(code, email)

        # Get usage_count after redemption
        after = manager.get_coupon(code)
        usage_after = after["usage_count"]

        assert usage_after == usage_before + 1, (
            f"Expected usage_count={usage_before + 1} after redemption, "
            f"got {usage_after}"
        )

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        email=email_strategy,
    )
    @settings(max_examples=100)
    def test_redemption_adds_email_to_used_by(self, name, max_usage, email):
        """After redeem_coupon, email appears in used_by list."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Redeem
        manager.redeem_coupon(code, email)

        # Verify email in used_by
        after = manager.get_coupon(code)
        assert email in after["used_by"], (
            f"Expected email '{email}' in used_by list after redemption, "
            f"got {after['used_by']}"
        )

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=2, max_value=10),
        emails=st.lists(email_strategy, min_size=2, max_size=10, unique=True),
    )
    @settings(max_examples=100)
    def test_multiple_redemptions_increment_correctly(self, name, max_usage, emails):
        """Multiple redemptions each increment usage_count by 1."""
        assume(len(emails) <= max_usage)

        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        for i, email in enumerate(emails):
            manager.redeem_coupon(code, email)

            after = manager.get_coupon(code)
            assert after["usage_count"] == i + 1, (
                f"After {i + 1} redemptions, expected usage_count={i + 1}, "
                f"got {after['usage_count']}"
            )
            assert email in after["used_by"], (
                f"Email '{email}' not found in used_by after redemption"
            )

        # Final check: all emails present
        final = manager.get_coupon(code)
        for email in emails:
            assert email in final["used_by"]


# =============================================================================
# Design Document Properties 4-7 (Tasks 2.2 - 2.5)
# =============================================================================


# --- Property 4: Coupon Code Generation Uniqueness and Charset ---

class TestDesignProperty4CouponCodeGenerationUniquenessAndCharset:
    """Property 4: Coupon Code Generation Uniqueness and Charset.

    *For any* set of existing coupon codes, `generate_coupon_code` should produce
    a code that is not in the existing set, consists only of uppercase ASCII letters
    and digits, and is exactly 8 characters long.

    **Validates: Requirements 3.2, 3.8**
    """

    @given(existing_codes=existing_codes_strategy)
    @settings(max_examples=50)
    def test_generated_code_unique_uppercase_digits_8_chars(self, existing_codes):
        """For any set of existing codes, generated code is unique, uppercase+digits, 8 chars."""
        code = generate_coupon_code(set(existing_codes))

        # Code is exactly 8 characters long
        assert len(code) == 8, f"Expected 8 chars, got {len(code)}: '{code}'"

        # Code consists only of uppercase ASCII letters and digits
        allowed_chars = set(string.ascii_uppercase + string.digits)
        for ch in code:
            assert ch in allowed_chars, (
                f"Character '{ch}' in code '{code}' is not in [A-Z0-9]"
            )

        # Code is not in the existing set (uniqueness)
        assert code not in existing_codes, (
            f"Generated code '{code}' collides with existing codes"
        )


# --- Property 5: Coupon Validation Reflects Usage State ---

class TestDesignProperty5CouponValidationReflectsUsageState:
    """Property 5: Coupon Validation Reflects Usage State.

    *For any* coupon with `usage_count` and `max_usage`, `validate_coupon` should
    return `(True, "Valid")` if and only if `usage_count < max_usage`, and
    `(False, "Coupon has reached its usage limit")` otherwise. For any code not
    in the coupon store, it should return `(False, "Invalid coupon code")`.

    **Validates: Requirements 3.3**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=1, max_value=50),
        usage_count=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=50)
    def test_validation_reflects_usage_state(self, name, max_usage, usage_count):
        """Valid iff usage_count < max_usage."""
        manager = _make_manager()

        # Create coupon and manually set usage_count to test the boundary
        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        code = coupon["code"]

        # Directly manipulate usage_count to test the property
        with manager._lock:
            manager._coupons[code]["usage_count"] = usage_count

        is_valid, message = manager.validate_coupon(code)

        if usage_count < max_usage:
            assert is_valid is True, (
                f"Expected valid=True for usage_count={usage_count} < max_usage={max_usage}"
            )
            assert message == "Valid"
        else:
            assert is_valid is False, (
                f"Expected valid=False for usage_count={usage_count} >= max_usage={max_usage}"
            )
            assert message == "Coupon has reached its usage limit"

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        nonexistent_code=st.text(alphabet=valid_code_charset, min_size=8, max_size=8),
    )
    @settings(max_examples=50)
    def test_nonexistent_code_returns_invalid(self, name, max_usage, nonexistent_code):
        """For any code not in the coupon store, returns (False, 'Invalid coupon code')."""
        manager = _make_manager()

        # Create a coupon so the store is not empty
        coupon = manager.create_coupon(name=name, max_usage=max_usage)

        # Ensure the nonexistent_code is actually not in the store
        assume(nonexistent_code != coupon["code"])

        is_valid, message = manager.validate_coupon(nonexistent_code)

        assert is_valid is False
        assert message == "Invalid coupon code"


# --- Property 6: Coupon Validate-and-Redeem Atomicity with Email Deduplication ---

class TestDesignProperty6ValidateAndRedeemAtomicity:
    """Property 6: Coupon Validate-and-Redeem Atomicity with Email Deduplication.

    *For any* valid coupon (usage_count < max_usage) and any email,
    `validate_and_redeem` should atomically increment `usage_count` by exactly 1
    and ensure the email appears in `used_by` at most once regardless of how many
    times the same email redeems.

    **Validates: Requirements 3.4**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=2, max_value=20),
        email=st.emails(),
    )
    @settings(max_examples=50)
    def test_validate_and_redeem_increments_usage_by_one(self, name, max_usage, email):
        """Atomically increments usage_count by exactly 1."""
        manager = CouponManager.__new__(CouponManager)
        manager._coupons = {}
        manager._lock = threading.Lock()

        # Set up a coupon directly in memory
        code = generate_coupon_code(set())
        manager._coupons[code] = {
            "name": name,
            "code": code,
            "max_usage": max_usage,
            "usage_count": 0,
            "used_by": [],
            "created_at": "2025-01-01 00:00",
            "updated_at": "2025-01-01 00:00",
        }

        # Mock _save_to_file to avoid file I/O
        with patch.object(manager, '_save_to_file'):
            # Get usage before
            usage_before = manager._coupons[code]["usage_count"]

            # Validate and redeem
            success, message, result = manager.validate_and_redeem(code, email)

            assert success is True
            assert message == "Valid"
            assert result is not None
            assert result["usage_count"] == usage_before + 1

    @given(
        name=coupon_name_strategy,
        max_usage=st.integers(min_value=3, max_value=20),
        email=st.emails(),
        num_redemptions=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=50)
    def test_email_deduplication_in_used_by(self, name, max_usage, email, num_redemptions):
        """Email appears in used_by at most once regardless of redemption count."""
        assume(num_redemptions <= max_usage)

        manager = CouponManager.__new__(CouponManager)
        manager._coupons = {}
        manager._lock = threading.Lock()

        # Set up a coupon directly in memory
        code = generate_coupon_code(set())
        manager._coupons[code] = {
            "name": name,
            "code": code,
            "max_usage": max_usage,
            "usage_count": 0,
            "used_by": [],
            "created_at": "2025-01-01 00:00",
            "updated_at": "2025-01-01 00:00",
        }

        # Mock _save_to_file to avoid file I/O
        with patch.object(manager, '_save_to_file'):
            # Redeem multiple times with the same email
            for _ in range(num_redemptions):
                success, message, result = manager.validate_and_redeem(code, email)
                assert success is True

            # Verify email appears at most once in used_by
            final = manager.get_coupon(code)
            email_count = final["used_by"].count(email)
            assert email_count == 1, (
                f"Email '{email}' appears {email_count} times in used_by after "
                f"{num_redemptions} redemptions (expected at most 1)"
            )

            # Verify usage_count was incremented only once (re-logins don't count)
            assert final["usage_count"] == 1


# --- Property 7: Coupon Code Immutability on Update ---

class TestDesignProperty7CouponCodeImmutabilityOnUpdate:
    """Property 7: Coupon Code Immutability on Update.

    *For any* coupon update request that includes a "code" field, `update_coupon`
    should raise `ValueError` regardless of the value provided, preserving the
    original code.

    **Validates: Requirements 3.5**
    """

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        new_code_value=st.text(min_size=0, max_size=30),
    )
    @settings(max_examples=50)
    def test_update_with_code_field_raises_valueerror(self, name, max_usage, new_code_value):
        """Any update including 'code' field raises ValueError."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        original_code = coupon["code"]

        # Attempt to update with a "code" field — should raise ValueError
        with pytest.raises(ValueError, match="Coupon code cannot be modified"):
            manager.update_coupon(original_code, code=new_code_value)

        # Verify the original code is preserved
        retrieved = manager.get_coupon(original_code)
        assert retrieved is not None
        assert retrieved["code"] == original_code

    @given(
        name=coupon_name_strategy,
        max_usage=valid_max_usage_strategy,
        new_code_value=st.text(min_size=0, max_size=30),
        new_name=coupon_name_strategy,
    )
    @settings(max_examples=50)
    def test_update_with_code_and_other_fields_raises_valueerror(self, name, max_usage, new_code_value, new_name):
        """Update including 'code' field alongside other fields still raises ValueError."""
        manager = _make_manager()

        coupon = manager.create_coupon(name=name, max_usage=max_usage)
        original_code = coupon["code"]

        # Attempt to update with "code" field alongside valid fields
        with pytest.raises(ValueError, match="Coupon code cannot be modified"):
            manager.update_coupon(original_code, code=new_code_value, name=new_name)

        # Verify the original coupon is unchanged
        retrieved = manager.get_coupon(original_code)
        assert retrieved is not None
        assert retrieved["code"] == original_code
        assert retrieved["name"] == name  # Original name preserved
