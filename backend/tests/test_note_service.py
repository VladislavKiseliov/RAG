from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services import note_service as note_service_module
from backend.services.note_service import NoteService
from backend.utils.exceptions import NoteNotFoundError


def _fake_note(**overrides):
    defaults = dict(
        id=1, guid=uuid.uuid4(), user_id=7, title="T", content="body",
        meta={}, links=[], tags=[], folder=None, reminder=None,
        pinned=False, follow_up=False, status="draft", chunk_count=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def llm_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(fake_uow_factory, llm_client) -> NoteService:
    return NoteService(uow_factory=fake_uow_factory, llm_client=llm_client)


async def test_create_note(fake_uow, service):
    fake_uow.notes.create_note.return_value = _fake_note(title="New")
    result = await service.create_note(user_id=7, title="New", content="")
    assert result.title == "New"
    fake_uow.commit.assert_awaited_once()


async def test_list_notes(fake_uow, service):
    fake_uow.notes.list_notes_for_user.return_value = [_fake_note(), _fake_note(id=2)]
    result = await service.list_notes(user_id=7)
    assert len(result) == 2


async def test_get_note_not_found_raises(fake_uow, service):
    fake_uow.notes.get_note_for_user.return_value = None
    with pytest.raises(NoteNotFoundError):
        await service.get_note(note_guid=uuid.uuid4(), user_id=7)


async def test_get_note_success(fake_uow, service):
    fake_uow.notes.get_note_for_user.return_value = _fake_note()
    result = await service.get_note(note_guid=uuid.uuid4(), user_id=7)
    assert result.status == "draft"


async def test_update_note_not_found_raises(fake_uow, service):
    fake_uow.notes.update_note.return_value = None
    with pytest.raises(NoteNotFoundError):
        await service.update_note(note_guid=uuid.uuid4(), user_id=7, data={"title": "x"})
    fake_uow.commit.assert_not_awaited()


async def test_update_note_success(fake_uow, service):
    fake_uow.notes.update_note.return_value = _fake_note(title="Updated")
    result = await service.update_note(note_guid=uuid.uuid4(), user_id=7, data={"title": "Updated"})
    assert result.title == "Updated"
    fake_uow.commit.assert_awaited_once()


async def test_delete_note_not_found_raises(fake_uow, service):
    fake_uow.notes.delete_note.return_value = False
    with pytest.raises(NoteNotFoundError):
        await service.delete_note(note_guid=uuid.uuid4(), user_id=7)


async def test_delete_note_ignores_rag_service_failure(fake_uow, service, monkeypatch):
    fake_uow.notes.delete_note.return_value = True
    monkeypatch.setattr(
        note_service_module.rag_client, "delete",
        AsyncMock(side_effect=httpx.ConnectError("unreachable")),
    )

    result = await service.delete_note(note_guid=uuid.uuid4(), user_id=7)

    assert result is True


async def test_trigger_index_not_found_raises(fake_uow, service):
    fake_uow.notes.update_note.return_value = None
    with pytest.raises(NoteNotFoundError):
        await service.trigger_index(note_guid=uuid.uuid4(), user_id=7)


async def test_trigger_index_success(fake_uow, service, monkeypatch):
    note_guid = uuid.uuid4()
    fake_uow.notes.update_note.return_value = _fake_note(guid=note_guid, status="indexing")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    monkeypatch.setattr(
        note_service_module.rag_client, "post", AsyncMock(return_value=response)
    )

    result = await service.trigger_index(note_guid=note_guid, user_id=7)

    assert result.status == "indexing"


async def test_trigger_index_marks_error_status_on_rag_failure(fake_uow, service, monkeypatch):
    note_guid = uuid.uuid4()
    fake_uow.notes.update_note.return_value = _fake_note(guid=note_guid, status="indexing")
    monkeypatch.setattr(
        note_service_module.rag_client, "post",
        AsyncMock(side_effect=httpx.ConnectError("unreachable")),
    )

    with pytest.raises(httpx.HTTPError):
        await service.trigger_index(note_guid=note_guid, user_id=7)

    fake_uow.notes.update_note.assert_any_await(note_guid, 7, {"status": "error"})


async def test_generate_note(fake_uow, service, llm_client):
    llm_client.generate_note.return_value = {
        "title": "Gen title", "content": "Gen content", "tags": ["a"],
    }
    fake_uow.notes.update_note.return_value = _fake_note(title="Gen title", content="Gen content")

    result = await service.generate_note(note_guid=uuid.uuid4(), user_id=7, raw_text="raw")

    assert result.title == "Gen title"
    llm_client.generate_note.assert_awaited_once_with(raw_text="raw")


async def test_generate_note_not_found_raises(fake_uow, service, llm_client):
    llm_client.generate_note.return_value = {"title": "x", "content": "y", "tags": []}
    fake_uow.notes.update_note.return_value = None

    with pytest.raises(NoteNotFoundError):
        await service.generate_note(note_guid=uuid.uuid4(), user_id=7, raw_text="raw")


async def test_mark_index_complete(fake_uow, service):
    note_guid = uuid.uuid4()
    await service.mark_index_complete(note_guid, "indexed", chunk_count=5)

    fake_uow.notes.update_note_by_guid.assert_awaited_once_with(
        note_guid, {"status": "indexed", "chunk_count": 5}
    )
    fake_uow.commit.assert_awaited_once()
