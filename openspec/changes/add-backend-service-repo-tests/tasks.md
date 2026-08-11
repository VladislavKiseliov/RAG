## 1. Prerequisite: fix sequence-collision bug

- [x] 1.1 In `backend/tests/conftest.py`'s `engine` fixture, after the seed inserts, advance the identity sequences for `Users`, `Chats`, `Messages` to `MAX(id)` via `pg_get_serial_sequence`/`setval` (portable — don't hardcode sequence names)
- [x] 1.2 Verify: a test using `test_user` (fresh insert relying on autoincrement) no longer collides with seeded Alice/Bob/Carol ids

## 2. Repository integration tests (real DB via testcontainers)

- [x] 2.1 `test_auth_repository.py` — refresh-token create/revoke/rotate CRUD, per `user-authentication` spec's rotation requirement
- [x] 2.2 `test_chat_repository.py` — `create_chat`/`get_chat`/`update_chat_title`/`delete_chat`/`get_user_active_chats`/`get_chat_member_guids`/`get_chat_by_guid_for_participant`/`get_chat_id_for_participant` — including the participant-scoping guarantee from `ai-chat-messaging`
- [x] 2.3 `test_message_repository.py` — message CRUD scoped to a chat
- [x] 2.4 `test_messenger_repository.py` — direct-chat participant queries
- [x] 2.5 `test_note_repository.py` — note CRUD scoped to owner, per `notes` spec's owner-only requirement
- [x] 2.6 `test_user_repository.py` — user CRUD, including the uniqueness constraint on login

## 3. UnitOfWork integration test (real DB)

- [x] 3.1 `test_unit_of_work.py` — commit persists across `.chats`/`.messages`/`.auth`/`.messenger`/`.notes`; rollback on exception discards changes

## 4. Service-layer tests — unit level, mocked `uow_factory` (no DB, per `inject-unit-of-work-dependency`)

- [x] 4.1 `test_chat_service.py` (mock `uow_factory`) — `create_chat`, `get_user_active_chats`, `update_chat_title`, `delete_chat`, `get_history`; explicitly test that `_resolve_chat_for_user` rejects a chat guid the user isn't a participant of (IDOR guard from `ai-chat-messaging`)
- [x] 4.2 `test_message_service.py` (mock `uow_factory`) — `resolve_chat` (never trusts a bare guid, per `messenger-websocket-realtime`), `save_message`, `mark_message_read`
- [x] 4.3 `test_messenger_service.py` (mock `uow_factory`) — `create_direct_chat`, `delete_direct_chat`, `get_user_chats`, `get_chat_messages` — participant-scoping per `messenger-direct-chat`
- [x] 4.4 `test_auth_service.py` (mock `uow_factory` + `auth_handler`) — `login`/`register`/`refresh`/`logout`/`get_user_from_token`; assert generic error on both unknown-login and wrong-password (per `user-authentication`'s anti-enumeration requirement)
- [x] 4.5 `test_note_service.py` (mock `uow_factory` + `llm_client`) — `create_note`/`list_notes`/`get_note`/`update_note`/`delete_note`/`trigger_index` status rollback on failure/`generate_note`/`mark_index_complete`, per `notes` spec

## 5. Service-layer tests — integration level, not yet on injected UoW (real DB)

- [x] 5.1 `test_user_service.py` (mock `auth_handler`) — CRUD + `delete_user_repo`/`update_user_role` guard rejections (self-delete, last-admin) per `admin-user-management`
- [x] 5.2 `test_conversation_service.py` (mock `llm_client`) — `process_message`, `update_summary`, `_maybe_trigger_summary` threshold behavior, degraded-response-not-persisted per `ai-chat-messaging`

## 6. Service-layer tests — pure unit (no DB)

- [x] 6.1 `test_auth_handler.py` — `create_access_token`/`decode_token` round-trip, `get_password_hash`/`verify_password`, `authenticate_user`
- [x] 6.2 `test_llm_client.py` (mock `httpx`) — `get_answer`, `generate_note`, `get_summary`, `stream_answer`
- [x] 6.3 `test_websocket_manager.py` (fake `WebSocket` objects) — `connect_socket`/`add_user_socket_connection`/`send_to_user`/`broadcast_to_users`/`remove_user_guid_to_websocket`

## 7. Verification

- [x] 7.1 Run the full `backend/tests` suite, confirm all new tests pass
- [x] 7.2 Remove the throwaway `backend/tests/test_conftest_smoke.py` from `migrate-tests-to-testcontainers` now that real tests exercise the same fixtures
