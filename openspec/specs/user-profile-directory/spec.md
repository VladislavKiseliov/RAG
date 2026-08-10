## Purpose
Self-service profile view/edit and colleague search for authenticated users.

## Requirements

### Requirement: Partial profile updates
Updating a profile MUST only change fields present in the request, leaving others untouched.

#### Scenario: Update only display name
- **WHEN** a user `PATCH`es their profile with only a new display name
- **THEN** login, role, and timestamps remain unchanged

### Requirement: Immutable identity fields via self-service
Login and role MUST NOT be changeable through the self-service profile endpoint.

#### Scenario: Attempt to change own role
- **WHEN** a user includes a `role` field in a profile update request
- **THEN** the role field is ignored (role changes only happen via admin-user-management)

### Requirement: Self-exclusion in colleague search
Searching for colleagues MUST exclude the requester's own account from results.

#### Scenario: User searches by common substring
- **WHEN** a user searches for colleagues by a name substring that matches their own name too
- **THEN** the requester's own account is not present in the results
