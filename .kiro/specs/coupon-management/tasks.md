# Implementation Plan: Coupon Management

## Overview

Implement a coupon management system for the PDN admin dashboard. The implementation follows the existing Flask blueprint pattern with JSON file persistence, thread-safe operations, and in-memory caching. The feature adds admin CRUD routes, a dashboard widget, and coupon-based login to the questionnaire.

## Tasks

- [x] 1. Create CouponManager module
  - [x] 1.1 Create `app/pdn_admin/coupon_manager.py` with CouponManager class
    - Implement `__init__` with JSON file path, in-memory cache, and threading lock
    - Implement `_load_coupons()` and `_save_to_file()` following the `UserManager` pattern (atomic write with .tmp file)
    - Implement `generate_coupon_code(existing_codes)` producing 8-char [A-Z0-9] codes
    - Implement `validate_custom_code(code)` checking 4-20 alphanumeric characters
    - Implement `get_status(coupon)` deriving "active" or "full" from usage_count vs max_usage
    - Create empty `app/data/coupons.json` with `{}` as initial content
    - _Requirements: 1.1, 1.3, 1.5, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_

  - [x] 1.2 Write property tests for code generation and validation
    - **Property 1: Code generation format** - For any generated code, verify 8 chars from [A-Z0-9]
    - **Property 2: Code uniqueness** - For any set of existing codes, new code is not a duplicate
    - **Property 5: Custom code validation** - Accept iff 4-20 alphanumeric chars
    - **Property 4: Status derivation** - Correct status from usage_count and max_usage
    - **Validates: Requirements 1.1, 1.4, 6.1, 6.2, 6.3, 2.2, 7.1, 7.2, 7.3**

  - [x] 1.3 Implement CRUD operations in CouponManager
    - Implement `create_coupon(name, max_usage, code=None)` with auto-generation and duplicate checking
    - Implement `get_coupon(code)` and `get_all_coupons()`
    - Implement `update_coupon(code, **updates)` with code immutability enforcement
    - Implement `delete_coupon(code)`
    - Implement `redeem_coupon(code, email)` incrementing usage_count and appending to used_by
    - Implement `validate_coupon(code)` returning (is_valid, message) tuple
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 4.1, 5.1, 5.2, 5.3, 5.4_

  - [x] 1.4 Write property tests for CRUD operations
    - **Property 3: Coupon creation round-trip** - All fields stored correctly after creation
    - **Property 6: Code immutability** - Code unchanged after any update
    - **Property 7: Update persistence** - Updated fields reflect new values
    - **Property 8: Deletion removes coupon** - Coupon not retrievable after delete
    - **Validates: Requirements 1.2, 1.3, 1.5, 3.1, 3.2, 3.3, 4.1**

- [x] 2. Checkpoint - Ensure CouponManager tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add admin API routes for coupon management
  - [x] 3.1 Add coupon routes to `app/pdn_admin/admin_routes.py`
    - `GET /pdn-admin/coupons` - List all coupons with status
    - `POST /pdn-admin/coupons` - Create coupon (accepts name, max_usage, optional code)
    - `PUT /pdn-admin/coupons/<code>` - Update coupon (name, max_usage)
    - `DELETE /pdn-admin/coupons/<code>` - Delete coupon
    - `GET /pdn-admin/coupons/<code>/usage` - Get usage details (used_by list)
    - All routes protected with `verify_session()`
    - Return appropriate HTTP status codes per error handling table in design
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.3, 3.1, 3.2, 3.3, 4.1_

  - [x] 3.2 Write unit tests for admin API routes
    - Test create coupon with and without custom code
    - Test list coupons returns all fields
    - Test update coupon with valid and invalid data
    - Test delete coupon
    - Test unauthorized access returns 401
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 3.1, 3.2, 4.1_

- [x] 4. Extend questionnaire login to accept coupon codes
  - [x] 4.1 Modify `app/pdn_diagnose/diagnosis_routes.py` login endpoint
    - Extend `POST /pdn-diagnose/login` to check for `coupon_code` field in request body
    - When `coupon_code` is present, validate via CouponManager instead of email/password
    - On valid coupon: create session with email (from request), call `redeem_coupon()`
    - On invalid/full coupon: return appropriate error message and status code
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.2 Write property tests for coupon validation and redemption
    - **Property 9: Coupon validation correctness** - Access granted iff code exists and not full
    - **Property 10: Redemption increments usage** - usage_count += 1 and email in used_by
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 5. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create admin dashboard coupon widget
  - [x] 6.1 Add coupon widget section to `app/pdn_admin/templates/admin_dashboard.html`
    - Add a "Coupons" section/card to the dashboard with Tailwind CSS styling matching existing gold/spiritual theme
    - Display coupon table with columns: Code, Name, Usage (count/max), Status badge, Actions
    - Status badges: green "active" badge, red "full" badge
    - Add "Create Coupon" button that opens a creation form/modal
    - Creation form: name input, max_usage number input, auto-generated code preview with "regenerate" button, optional custom code override toggle
    - Add edit button per row (opens inline edit or modal for name and max_usage)
    - Add delete button per row with confirmation dialog
    - Add "View Usage" button per row that shows modal with list of redeemed emails
    - Wire all actions to the admin API routes using fetch() with session_token
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 7.1, 7.2, 7.3_

  - [x] 6.2 Add coupon code input to diagnose login page
    - Modify `app/pdn_diagnose/templates/diagnose_login.html`
    - Add a "Login with Coupon" section/tab below or alongside the existing email/password form
    - Include email input and coupon code input field
    - On submit, POST to `/pdn-diagnose/login` with `coupon_code` and `email` fields
    - Display appropriate error messages for invalid/full coupons
    - Style consistently with existing Tailwind theme
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 6.3 Display coupon code as read-only in user form
    - Modify `app/pdn_diagnose/templates/user_form.html`
    - When session contains a `coupon_code` value, display it as a read-only input field on the user form
    - Hide the field if no coupon was used for login
    - Pass `coupon_code` from session to the template in the route handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 6.4 Add coupon column to diagnosed users table
    - Modify `app/pdn_admin/templates/admin_dashboard.html` to add a "קופון" column to the נתוני מאובחנים table
    - Store the coupon code used by each user in their user record (in users.json) when they redeem a coupon
    - Display the coupon code in the table; show dash or empty for users without a coupon
    - Ensure the existing search input also searches the coupon column
    - Add sort capability on the coupon column (clicking column header)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The project already uses Hypothesis for property-based testing
- All JSON file operations use atomic writes (write to .tmp then rename) for safety
- The CouponManager follows the same singleton pattern as UserManager
- Admin routes use the existing `verify_session()` authentication mechanism
- The UI follows the existing Tailwind CSS gold/spiritual theme
