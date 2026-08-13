## 1. API wiring

- [x] 1.1 Add `ADMIN_USER: (id) => \`/admin/users/repo/${id}\`` to `frontend/src/config/api.jsx` (alongside the existing `ADMIN_USER_ROLE`)
- [x] 1.2 Add `deleteUser` to `frontend/src/hooks/useAdmin.js`: calls `api.delete(ENDPOINTS.ADMIN_USER(userId))`, removes the user from `users` state on success, calls `showError(e.message)` on failure (same try/catch pattern as `toggleUserRole`)
- [x] 1.3 Export `deleteUser` from the hook's return object

## 2. UI

- [x] 2.1 Add a delete action to each row in `frontend/src/components/admin/UsersTab.jsx`
- [x] 2.2 Add a confirmation step before the delete request fires (two-step, matching the `confirmDeleteId` pattern already used in `ChatList.jsx` — not the direct-call pattern `DocumentsTab.jsx` uses for documents, since account deletion is higher-stakes)

## 3. Verification

- [ ] 3.1 Manually verify: deleting a non-admin user removes it from the list
- [ ] 3.2 Manually verify: attempting to delete your own account shows the backend's guard error via the toast, row stays
- [ ] 3.3 Manually verify: attempting to delete the last remaining admin shows the backend's guard error via the toast, row stays
- [x] 3.4 Run `npm run build` in `frontend/` to confirm no syntax/import errors
