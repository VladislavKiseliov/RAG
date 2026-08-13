## Purpose
Frontend admin UI for system health, document operations, user role management, and Celery task monitoring. Mostly real; a few pieces (personal-doc stats, Qdrant stats, document rename, user block toggle) are local-state-only with no backing endpoint.

## Requirements

### Requirement: Self-stopping document status polling
While any document is in a `processing`-equivalent state, the document list MUST be re-fetched periodically; polling MUST stop automatically once no document is active.

#### Scenario: All documents finish processing
- **WHEN** the last actively-processing document transitions to a terminal state
- **THEN** polling stops, it does not continue indefinitely

### Requirement: Eight backend states collapsed to three UI states
Raw document status values from rag_service (`pending/uploading/processing/extracting/indexing/completed/error/duplicate`) MUST be collapsed into three UI states (`indexed/processing/error`) with a full label map available for detail views.

#### Scenario: A document is in the `extracting` backend state
- **WHEN** the document list is rendered
- **THEN** it displays under the `processing` UI state, with `extracting` available as the detailed label on hover/detail

### Requirement: Mock-backed pieces are not presented as real data
`MOCK_PERSONAL_DOCS`/`MOCK_QDRANT` stats, document title rename, and user active/block toggle MUST NOT silently imply server persistence — there is no backing endpoint for any of these today.

#### Scenario: An admin renames a document title or toggles a user's active state
- **WHEN** either action is performed
- **THEN** the change is local UI state only and does not survive a page refresh, since no PATCH endpoint exists for it

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
