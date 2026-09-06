# Requirements Document

## Introduction

The Coupon Management feature enables administrators of the PDN system to create, manage, and track promotional coupons that grant users access to the questionnaire. Each coupon has a usage limit, an auto-generated code (overridable by admin), and status tracking. Users enter a coupon code on the questionnaire login page to gain access without needing individual credentials.

## Glossary

- **Coupon_Manager**: The backend module responsible for creating, reading, updating, and deleting coupon records in the JSON data store.
- **Admin_Dashboard**: The PDN admin web interface at /pdn-admin/dashboard where administrators manage system resources.
- **Coupon_Widget**: The UI component within the Admin Dashboard that displays coupon information and provides management controls.
- **Coupon_Code**: An 8-character alphanumeric string that uniquely identifies a coupon.
- **Code_Generator**: The utility that produces random 8-character alphanumeric coupon codes.
- **Usage_Count**: The number of times a coupon has been redeemed by distinct users.
- **Max_Usage**: The maximum number of users allowed to redeem a given coupon.
- **Coupon_Status**: A derived state indicating whether a coupon is active, expired, or full.
- **Diagnose_Login_Page**: The questionnaire login page at /pdn-diagnose/ where users authenticate to access the questionnaire.
- **Coupon_Validator**: The component that checks whether a submitted coupon code is valid and has remaining uses.

## Requirements

### Requirement 1: Create Coupons

**User Story:** As an administrator, I want to create new coupons with a usage limit, so that I can control how many users can access the questionnaire through each coupon.

#### Acceptance Criteria

1. WHEN an administrator submits a create coupon request without a custom code, THE Code_Generator SHALL produce a unique 8-character alphanumeric code.
2. WHEN an administrator provides a custom coupon code, THE Coupon_Manager SHALL use the provided code instead of generating one.
3. WHEN an administrator creates a coupon, THE Coupon_Manager SHALL store the coupon with a name, code, max_usage limit, creation timestamp, and initial usage_count of zero.
4. IF a coupon code already exists in the data store, THEN THE Coupon_Manager SHALL reject the creation and return a duplicate code error.
5. WHEN a coupon is created, THE Coupon_Manager SHALL persist the coupon to the coupons.json file immediately.

### Requirement 2: View Coupons

**User Story:** As an administrator, I want to view all coupons and their usage statistics, so that I can monitor coupon utilization and plan accordingly.

#### Acceptance Criteria

1. WHEN an administrator opens the Coupon_Widget, THE Admin_Dashboard SHALL display a list of all coupons with their code, name, usage_count, max_usage, and status.
2. WHEN displaying a coupon, THE Coupon_Widget SHALL show the coupon status as "active" when usage_count is less than max_usage, and "full" when usage_count equals or exceeds max_usage.
3. WHEN an administrator views a specific coupon, THE Coupon_Widget SHALL display the list of user emails that have redeemed the coupon.

### Requirement 3: Edit Coupons

**User Story:** As an administrator, I want to edit existing coupons, so that I can adjust usage limits or coupon names as needs change.

#### Acceptance Criteria

1. WHEN an administrator updates a coupon's max_usage, THE Coupon_Manager SHALL persist the new limit and recalculate the coupon status.
2. WHEN an administrator updates a coupon's name, THE Coupon_Manager SHALL persist the new name.
3. THE Coupon_Manager SHALL NOT allow editing of the coupon code after creation.

### Requirement 4: Delete Coupons

**User Story:** As an administrator, I want to delete coupons, so that I can remove coupons that are no longer needed.

#### Acceptance Criteria

1. WHEN an administrator deletes a coupon, THE Coupon_Manager SHALL remove the coupon record from the coupons.json file.
2. WHEN a coupon is deleted, THE Coupon_Manager SHALL preserve historical usage data by keeping redeemed user records intact in the users who already used the coupon.

### Requirement 5: Validate Coupon on Questionnaire Login

**User Story:** As a user, I want to enter a coupon code on the questionnaire login page, so that I can access the questionnaire without individual credentials.

#### Acceptance Criteria

1. WHEN a user submits a valid coupon code on the Diagnose_Login_Page, THE Coupon_Validator SHALL grant access to the questionnaire.
2. WHEN a user submits a coupon code that has reached its max_usage, THE Coupon_Validator SHALL reject the login and display a "coupon fully used" message.
3. WHEN a user submits a non-existent coupon code, THE Coupon_Validator SHALL reject the login and display an "invalid coupon" message.
4. WHEN a user successfully logs in with a coupon, THE Coupon_Manager SHALL increment the coupon's usage_count by one and record the user's email in the coupon's usage list.

### Requirement 6: Auto-Generate Coupon Codes

**User Story:** As an administrator, I want coupon codes to be auto-generated, so that I can quickly create coupons without manually inventing unique codes.

#### Acceptance Criteria

1. THE Code_Generator SHALL produce codes consisting of exactly 8 characters from the set [A-Z, 0-9].
2. THE Code_Generator SHALL ensure each generated code is unique by checking against existing codes in the data store.
3. WHEN an administrator overrides the auto-generated code, THE Coupon_Manager SHALL validate that the custom code is between 4 and 20 alphanumeric characters.

### Requirement 7: Coupon Status Display

**User Story:** As an administrator, I want to see the status of each coupon at a glance, so that I can quickly identify which coupons are still available.

#### Acceptance Criteria

1. THE Coupon_Widget SHALL display each coupon's status as one of: "active", "full".
2. WHEN a coupon's usage_count is less than its max_usage, THE Coupon_Widget SHALL display the status as "active".
3. WHEN a coupon's usage_count equals or exceeds its max_usage, THE Coupon_Widget SHALL display the status as "full".

### Requirement 8: Display Coupon Code in User Form

**User Story:** As a user who logged in with a coupon, I want to see the coupon code displayed on the questionnaire user form, so that I know which coupon granted me access.

#### Acceptance Criteria

1. WHEN a user logs in with a coupon code, THE Questionnaire_UI SHALL display the coupon code as a read-only field on the user details form (user_form.html).
2. THE coupon code field SHALL be non-editable (read-only) to prevent modification.
3. IF the user did not log in with a coupon, THE Questionnaire_UI SHALL NOT display the coupon code field.

### Requirement 9: Coupon Column in Diagnosed Users Table

**User Story:** As an administrator, I want to see which coupon each diagnosed user used in the נתוני מאובחנים table, so that I can track coupon effectiveness and filter users by coupon.

#### Acceptance Criteria

1. THE Admin_Dashboard SHALL display a "קופון" (coupon) column in the נתוני מאובחנים (diagnosed users) table showing the coupon code used by each user.
2. WHEN a user did not use a coupon, THE Admin_Dashboard SHALL display an empty value or dash in the coupon column.
3. THE Admin_Dashboard SHALL allow searching/filtering the diagnosed users table by coupon code via the existing search input.
4. THE Admin_Dashboard SHALL allow sorting the diagnosed users table by the coupon column.
