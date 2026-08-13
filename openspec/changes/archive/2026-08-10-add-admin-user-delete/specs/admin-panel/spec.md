## ADDED Requirements

### Requirement: Admin can delete a user from the Users tab
The Users tab MUST provide an action to delete a user account, backed by the real `DELETE /admin/users/repo/{id}` endpoint.

#### Scenario: Admin deletes a user
- **WHEN** an admin confirms deletion of a user
- **THEN** the request is sent to `DELETE /admin/users/repo/{id}` and, on success, the user row is removed from the list

### Requirement: Deletion requires confirmation before the request is sent
The delete action MUST require an explicit confirmation step; a single click MUST NOT immediately delete the account.

#### Scenario: Admin clicks delete
- **WHEN** an admin clicks the delete action for a user
- **THEN** a confirmation step is shown, and the DELETE request is only sent after the admin confirms

### Requirement: Backend guard rejections are surfaced to the admin
If the backend rejects the deletion (self-deletion or last-admin protection, per `admin-user-management`), the failure MUST be shown to the admin via the shared error toast, not silently ignored.

#### Scenario: Admin attempts to delete their own account or the last remaining admin
- **WHEN** the backend rejects the DELETE request with a guard error
- **THEN** the admin sees the error message, and the user row remains in the list unchanged
