## Why

The admin panel's Users tab can toggle a user's admin role, but has no way to delete a user account. The backend already exposes `DELETE /admin/users/repo/{id}` (`backend/api/admin_routes.py:237`, `UserService.delete_user_repo`) with self-deletion and last-admin guardrails already in place and already documented in `admin-user-management` — the gap is entirely on the frontend, which never wires a delete action to it.

## What Changes

- Add a delete action (button + confirmation step) to the admin Users tab.
- Wire it to the existing `DELETE /admin/users/repo/{id}` endpoint via a new `deleteUser` function in `useAdmin.js` and a new `ADMIN_USER` endpoint constant.
- Surface success (row removed) and failure (e.g. last-admin/self-delete rejection) to the admin via the existing shared error toast — the backend already returns clear error responses for both guard cases, this change only needs to display them.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-panel`: adds a Requirement for deleting a user from the Users tab, including confirmation-before-delete and surfacing backend guard errors (self-delete, last-admin) to the admin.

## Impact

- Affected code: `frontend/src/hooks/useAdmin.js`, `frontend/src/components/admin/UsersTab.jsx`, `frontend/src/config/api.jsx` (new `ADMIN_USER` endpoint constant).
- No backend changes — `DELETE /admin/users/repo/{id}` and its guardrails already exist and are already covered by `admin-user-management` (no delta needed there).
- No new dependencies.
