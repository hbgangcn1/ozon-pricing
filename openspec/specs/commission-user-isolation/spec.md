## Purpose

commission-user-isolation capability spec.

## Requirements


### Requirement: Commission categories are user-scoped
The system SHALL associate each commission category with a specific user via a `user_id` foreign key. Each user SHALL only see and manage their own commission categories. The `name` uniqueness constraint SHALL be per-user (user_id + name), not global.

#### Scenario: User creates a commission category
- **WHEN** an authenticated user creates a commission category with name "日化品"
- **THEN** the system creates it with user_id set to the current user's ID, and returns success

#### Scenario: User cannot see other users' categories
- **WHEN** user A has category "日化品" and user B queries their categories
- **THEN** user B's response SHALL NOT include user A's "日化品" category

#### Scenario: Two users can have same category name
- **WHEN** user A creates category "日化品" and user B creates category "日化品"
- **THEN** both operations succeed because uniqueness is per-user

### Requirement: Commission CRUD requires authentication not admin
The system SHALL allow any authenticated user (not just admin) to create, read, update, and delete their own commission categories. The `require_admin` dependency SHALL be replaced with `get_current_user_id`.

#### Scenario: Non-admin user manages categories
- **WHEN** a user with role "user" creates/updates/deletes a commission category
- **THEN** the operation succeeds (previously required admin role)

#### Scenario: User cannot modify another user's category
- **WHEN** user A attempts to update or delete a category belonging to user B
- **THEN** the system returns 404 (category not found for this user)

### Requirement: Pricing engine uses user-scoped commissions
The system SHALL pass the current user's ID to the pricing engine when calculating commissions. The pricing engine SHALL only use commission categories belonging to the current user.

#### Scenario: Pricing calculation uses correct user commissions
- **WHEN** user A has commission rate 12% for "日化品" and user B has 15% for "日化品"
- **THEN** pricing calculation for user A uses 12%, and for user B uses 15%

### Requirement: Existing commission data migrates to admin
The system SHALL provide an Alembic migration that adds `user_id` column to `commission_categories` table and assigns all existing records to the admin user (user with role="admin"). The migration SHALL change the unique constraint from `name` to `(user_id, name)`.

#### Scenario: Migration assigns existing data to admin
- **WHEN** the Alembic migration runs on a database with existing global commission categories
- **THEN** all existing records have `user_id` set to the admin user's ID, and the unique constraint is updated to (user_id, name)

### Requirement: New users start with empty commissions
The system SHALL NOT auto-populate commission categories for newly registered users. New users start with zero commission categories.

#### Scenario: New user registration
- **WHEN** a new user registers
- **THEN** they have zero commission categories in the database
