from __future__ import annotations

import uuid

from sqlalchemy import select

from backend.models.database_models import ReadStatus


async def test_get_message_by_guid(messenger_repository, message_repository, test_ai_chat):
    message = await message_repository.add_message(test_ai_chat.id, content="hi")
    found = await messenger_repository.get_message_by_guid(message.guid)
    assert found.id == message.id


async def test_get_message_by_guid_not_found(messenger_repository):
    assert await messenger_repository.get_message_by_guid(uuid.uuid4()) is None


async def test_upsert_read_status_creates_then_updates(
    messenger_repository, message_repository, test_direct_chat, test_user, session_factory
):
    msg1 = await message_repository.add_message(test_direct_chat.id, content="one", user_id=test_user.id)
    msg2 = await message_repository.add_message(test_direct_chat.id, content="two", user_id=test_user.id)

    created = await messenger_repository.upsert_read_status(test_user.id, test_direct_chat.id, msg1.id)
    assert created.last_read_message_id == msg1.id

    updated = await messenger_repository.upsert_read_status(test_user.id, test_direct_chat.id, msg2.id)
    assert updated.last_read_message_id == msg2.id

    async with session_factory() as session:
        result = await session.execute(
            select(ReadStatus).where(
                ReadStatus.user_id == test_user.id, ReadStatus.chat_id == test_direct_chat.id
            )
        )
        rows = result.scalars().all()
    assert len(rows) == 1
