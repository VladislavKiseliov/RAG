## Purpose
Admin-only CRUD over user accounts and role changes, with guardrails against locking out administration.

## Requirements

### Requirement: Admin-only access
Every endpoint in this capability MUST require an authenticated user with the admin role.

#### Scenario: Non-admin calls admin user endpoint
- **WHEN** a non-admin authenticated user calls any `/admin/users/*` endpoint
- **THEN** the request is rejected before reaching business logic

### Requirement: No self-deletion or self-demotion
An admin MUST NOT be able to delete their own account or remove their own admin role.

#### Scenario: Admin tries to delete own account
- **WHEN** an admin calls delete on their own user id
- **THEN** the request is rejected with `SelfActionForbiddenError`

### Requirement: Last-admin protection
The system MUST refuse to demote or delete the last remaining admin account.

#### Scenario: Demoting the sole remaining admin
- **WHEN** an admin attempts to change the role of the only remaining superuser to a non-admin role
- **THEN** the request is rejected with `LastAdminError` and the role is unchanged

### Requirement: Conflict on duplicate login
Updating a user's login to one already in use MUST fail with a conflict, not overwrite silently.

#### Scenario: Rename user to an existing login
- **WHEN** an admin updates a user's login to a value already used by another account
- **THEN** the request returns 409 and no user record is modified
