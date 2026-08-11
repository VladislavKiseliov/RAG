## 1. Service constructors

- [x] 1.1 `backend/services/auth_service.py` — `__init__` takes `uow_factory: Callable[[], UnitOfWork]` instead of `session_factory`; replace all 10 inline `UnitOfWork(self._sf)` call sites (`login` x2, `register` x2, `refresh` x3, `logout` x2, `get_user_from_token` x1) with `self._uow_factory()`
- [x] 1.2 `backend/services/chat_service.py` — same pattern, 5 call sites (`create_chat`, `get_user_active_chats`, `update_chat_title`, `delete_chat`, `get_history` — task description missed `get_user_active_chats`, corrected here)
- [x] 1.3 `backend/services/messenger/message_service.py` — same pattern, 4 call sites (`resolve_chat`, `get_chat_member_guids`, `save_message`, `mark_message_read`)
- [x] 1.4 `backend/services/messenger/messenger_service.py` — same pattern, 4 call sites (`create_direct_chat`, `delete_direct_chat`, `get_user_chats`, `get_chat_messages`)
- [x] 1.5 `backend/services/note_service.py` — same pattern, 9 call sites (`create_note`, `list_notes`, `get_note`, `update_note`, `delete_note`, `trigger_index` x2, `generate_note`, `mark_index_complete` — task description undercounted as 7, corrected here)

## 2. DI wiring

- [x] 2.1 `backend/dependencies.py` — update `get_auth_service`, `get_chat_service`, `get_message_service`, `get_messenger_service`, `get_note_service` to construct `uow_factory=lambda: UnitOfWork(container.session_factory)` instead of passing `session_factory` directly

## 3. Verification

- [x] 3.1 Run backend's test suite, confirm no regressions (2/2 pass — only the testcontainers smoke test exists so far, real service tests land with `add-backend-service-repo-tests`)
- [x] 3.2 Manual smoke test through the running app (backend restarted to pick up changes; two throwaway users registered, exercised, then fully cleaned up incl. direct DB delete of the accounts): register/login/logout (`AuthService`) ✓, create_chat + get_history (`ChatService`) ✓, create_note (`NoteService`) ✓, create_direct_chat (`MessengerService`) ✓ all real HTTP round-trips through nginx→backend. `MessageService` not exercised (its only real call site is the WebSocket message-send path, not REST) — same refactor pattern as the other four, DI wiring already proven correct by them
- [x] 3.3 Grep for any other construction site of these five services outside `backend/dependencies.py` (expected: none, per the check already done during design, but re-verify after the edits in case something was missed) — confirmed: none
