from __future__ import annotations

import uuid


async def test_create_note(note_repository, test_user):
    note = await note_repository.create_note(test_user.id, title="T", content="body")
    assert note.id is not None
    assert note.user_id == test_user.id
    assert note.title == "T"
    assert note.status == "draft"


async def test_get_note_by_guid(note_repository, test_user):
    note = await note_repository.create_note(test_user.id, title="T", content="body")
    found = await note_repository.get_note_by_guid(note.guid)
    assert found.id == note.id

    assert await note_repository.get_note_by_guid(uuid.uuid4()) is None


async def test_get_note_for_user_is_owner_scoped(note_repository, test_user, test_user_bob):
    note = await note_repository.create_note(test_user.id, title="T", content="body")

    assert (await note_repository.get_note_for_user(note.guid, test_user.id)).id == note.id
    assert await note_repository.get_note_for_user(note.guid, test_user_bob.id) is None


async def test_list_notes_for_user(note_repository, test_user, test_user_bob):
    await note_repository.create_note(test_user.id, title="A", content="")
    await note_repository.create_note(test_user.id, title="B", content="")
    await note_repository.create_note(test_user_bob.id, title="C", content="")

    notes = await note_repository.list_notes_for_user(test_user.id)
    assert {n.title for n in notes} == {"A", "B"}


async def test_update_note_is_owner_scoped(note_repository, test_user, test_user_bob):
    note = await note_repository.create_note(test_user.id, title="Old", content="")

    updated = await note_repository.update_note(note.guid, test_user.id, {"title": "New"})
    assert updated.title == "New"

    rejected = await note_repository.update_note(note.guid, test_user_bob.id, {"title": "Hacked"})
    assert rejected is None


async def test_update_note_by_guid_ignores_owner(note_repository, test_user):
    note = await note_repository.create_note(test_user.id, title="Old", content="")

    updated = await note_repository.update_note_by_guid(note.guid, {"status": "indexed"})
    assert updated.status == "indexed"


async def test_delete_note_is_owner_scoped(note_repository, test_user, test_user_bob):
    note = await note_repository.create_note(test_user.id, title="Bye", content="")

    assert await note_repository.delete_note(note.guid, test_user_bob.id) is False
    assert await note_repository.delete_note(note.guid, test_user.id) is True
    assert await note_repository.get_note_by_guid(note.guid) is None
