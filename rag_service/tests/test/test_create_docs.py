import pytest
from types import SimpleNamespace

from rag_service.application.document_service import DocumentService
from rag_service.models import DocumentStatus

class FakeRepository:
    def __init__(self):
        self.created_args = None

    async def get_document_by_hash(self, file_hash: str):
        return SimpleNamespace(
            id="existing-doc-id",
            status=DocumentStatus.completed,
        )

    async def create_doc(self, filename, file_hash, meta, doc_id=None):
        self.created_called = True
        return "new-doc-id"

    # async def get_document_by_hash(self, file_hash: str):
    #     return None

    async def create_doc(self, filename, file_hash, meta, doc_id=None):
        self.created_args = {
            "filename": filename,
            "file_hash": file_hash,
            "meta": meta,
            "doc_id": doc_id,
        }
        return "new-doc-id"


class FakeSession:
    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_create_doc_creates_new_document_when_hash_not_exists():
    session = FakeSession()
    service = DocumentService(session)
    fake_repo = FakeRepository()
    service._repo = fake_repo

    result = await service.create_doc(
        filename="report.pdf",
        file_hash="hash-123",
        meta={"source": "upload"},
    )

    assert result == "new-doc-id"
    assert fake_repo.created_args == {
        "filename": "report.pdf",
        "file_hash": "hash-123",
        "meta": {"source": "upload"},
        "doc_id": None,
    }


@pytest.mark.asyncio
async def test_create_doc_returns_existing_completed_document():
    session = FakeSession()
    service = DocumentService(session)
    fake_repo = FakeRepository()
    service._repo = fake_repo

    result = await service.create_doc(
        filename="report.pdf",
        file_hash="hash-123",
        meta={"source": "upload"},
    )

    assert result == "existing-doc-id"
    assert fake_repo.created_called is False