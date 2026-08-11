from __future__ import annotations

import pytest

from backend.models.database_models import ChatType, Chats, Notes
from backend.services.unit_of_work import UnitOfWork


async def test_commit_persists_across_repositories(session_factory, test_user):
    async with UnitOfWork(session_factory) as uow:
        chat = await uow.chats.create_chat(test_user.id, "UoW chat", ChatType.GROUP)
        note = await uow.notes.create_note(test_user.id, title="UoW note", content="")
        await uow.commit()

    try:
        async with session_factory() as session:
            assert await session.get(Chats, chat.id) is not None
            assert await session.get(Notes, note.id) is not None
    finally:
        async with UnitOfWork(session_factory) as cleanup:
            await cleanup.chats.delete_chat(chat.id)
            await cleanup.notes.delete_note(note.guid, test_user.id)
            await cleanup.commit()


async def test_rollback_on_exception_discards_changes(session_factory, test_user):
    chat_id = None
    with pytest.raises(RuntimeError):
        async with UnitOfWork(session_factory) as uow:
            chat = await uow.chats.create_chat(test_user.id, "Should vanish", ChatType.GROUP)
            chat_id = chat.id
            raise RuntimeError("boom")

    async with session_factory() as session:
        assert await session.get(Chats, chat_id) is None


async def test_exiting_without_commit_does_not_persist(session_factory, test_user):
    async with UnitOfWork(session_factory) as uow:
        chat = await uow.chats.create_chat(test_user.id, "Never committed", ChatType.GROUP)
        chat_id = chat.id
    # exited normally without calling uow.commit()

    async with session_factory() as session:
        assert await session.get(Chats, chat_id) is None
