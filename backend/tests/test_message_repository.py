from __future__ import annotations


async def test_add_message(message_repository, test_ai_chat, test_user):
    message = await message_repository.add_message(
        test_ai_chat.id, content="hi", role="user", user_id=test_user.id
    )
    assert message.id is not None
    assert message.content == "hi"
    assert message.chat_id == test_ai_chat.id


async def test_get_history_order_and_limit(message_repository, test_ai_chat):
    for i in range(5):
        await message_repository.add_message(test_ai_chat.id, content=f"msg-{i}")

    history = await message_repository.get_history(test_ai_chat.id, limit=3)
    assert [m.content for m in history] == ["msg-2", "msg-3", "msg-4"]


async def test_get_recent_order_and_limit(message_repository, test_ai_chat):
    for i in range(4):
        await message_repository.add_message(test_ai_chat.id, content=f"m-{i}")

    recent = await message_repository.get_recent(test_ai_chat.id, limit=2)
    assert [m.content for m in recent] == ["m-2", "m-3"]


async def test_count_after(message_repository, test_ai_chat):
    ids = []
    for i in range(4):
        msg = await message_repository.add_message(test_ai_chat.id, content=f"c-{i}")
        ids.append(msg.id)

    assert await message_repository.count_after(test_ai_chat.id) == 4
    assert await message_repository.count_after(test_ai_chat.id, after_id=ids[1]) == 2


async def test_get_messages_after(message_repository, test_ai_chat):
    ids = []
    for i in range(4):
        msg = await message_repository.add_message(test_ai_chat.id, content=f"a-{i}")
        ids.append(msg.id)

    after = await message_repository.get_messages_after(test_ai_chat.id, after_id=ids[1], limit=10)
    assert [m.content for m in after] == ["a-2", "a-3"]


async def test_get_messages_paginated(message_repository, test_ai_chat, test_user):
    for i in range(5):
        await message_repository.add_message(test_ai_chat.id, content=f"p-{i}", user_id=test_user.id)

    page1 = await message_repository.get_messages_paginated(test_ai_chat.id, limit=2, offset=0)
    page2 = await message_repository.get_messages_paginated(test_ai_chat.id, limit=2, offset=2)

    assert [m.content for m in page1] == ["p-3", "p-4"]
    assert [m.content for m in page2] == ["p-1", "p-2"]
    assert page1[0].user.id == test_user.id
