import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_service.workers.ingestion_service import IngestionResult, IngestionService
from rag_service.models import DocumentStatus


@pytest.fixture
def document_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.create_doc = AsyncMock()
    mock.add_parent_chunks = AsyncMock()
    mock.set_status = AsyncMock()
    return mock


@pytest.fixture
def vector_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def vector_indexing_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.upsert_points = AsyncMock()
    return mock


@pytest.fixture
def ingestion_service(
    document_service_mock: AsyncMock,
    vector_provider_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> IngestionService:
    return IngestionService(
        document_service=document_service_mock,
        vector_provider=vector_provider_mock,
        vector_indexing_service=vector_indexing_service_mock,
        s3_storage=SimpleNamespace(),
        vector_timeout_seconds=1.0,
    )


def test_calculate_file_hash_returns_sha256_hex() -> None:
    content = b"hello world"
    result = IngestionService.calculate_file_hash(content)
    assert result == hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_ingest_path_raises_for_missing_file(ingestion_service: IngestionService) -> None:
    with pytest.raises(FileNotFoundError):
        await ingestion_service.ingest_path("D:/missing-file.pdf")


@pytest.mark.asyncio
async def test_ingest_path_raises_for_empty_file(tmp_path, ingestion_service: IngestionService) -> None:
    file_path = tmp_path / "empty.pdf"
    file_path.write_bytes(b"")

    with pytest.raises(ValueError, match="Empty file"):
        await ingestion_service.ingest_path(str(file_path))


@pytest.mark.asyncio
async def test_ingest_path_runs_happy_path(
    tmp_path,
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> None:
    file_path = tmp_path / "manual.pdf"
    file_path.write_bytes(b"pdf-bytes")
    created_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    document_service_mock.create_doc.return_value = created_id
    ingestion_service._chunker = MagicMock()
    ingestion_service._chunker.process.return_value = (
        [{"id": parent_id, "text": "Parent text", "headers": {"h1": "A"}, "page_num": 1}],
        [{"id": child_id, "text": "Child text", "parent_id": parent_id, "headers": {"h1": "A"}, "source": str(file_path)}],
    )

    result = await ingestion_service.ingest_path(str(file_path), meta={"source": "test"})

    assert result == IngestionResult(created_id, DocumentStatus.completed)
    document_service_mock.create_doc.assert_awaited_once_with(
        filename="manual.pdf",
        file_hash=hashlib.sha256(b"pdf-bytes").hexdigest(),
        meta={"source": "test"},
        doc_id=None,
    )
    document_service_mock.add_parent_chunks.assert_awaited_once_with(created_id, [{"id": parent_id, "text": "Parent text", "headers": {"h1": "A"}, "page_num": 1}])
    vector_indexing_service_mock.upsert_points.assert_awaited_once()
    (points_arg,) = vector_indexing_service_mock.upsert_points.await_args.args
    assert points_arg == [
        {
            "id": child_id,
            "text": "Child text",
            "payload": {
                "parent_id": parent_id,
                "headers": {"h1": "A"},
                "source": str(file_path),
                "doc_id": str(created_id),
            },
        }
    ]
    document_service_mock.set_status.assert_awaited_once_with(created_id, DocumentStatus.completed, chunk_count=1)


@pytest.mark.asyncio
async def test_ingest_path_uses_explicit_doc_id(
    tmp_path,
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
) -> None:
    file_path = tmp_path / "manual.pdf"
    file_path.write_bytes(b"pdf-bytes")
    explicit_id = uuid.uuid4()
    document_service_mock.create_doc.return_value = explicit_id
    ingestion_service._chunker = MagicMock()
    ingestion_service._chunker.process.return_value = (
        [{"id": uuid.uuid4(), "text": "Parent text"}],
        [{"text": "Child text", "parent_id": uuid.uuid4()}],
    )

    await ingestion_service.ingest_path(str(file_path), doc_id=explicit_id)

    document_service_mock.create_doc.assert_awaited_once_with(
        filename="manual.pdf",
        file_hash=hashlib.sha256(b"pdf-bytes").hexdigest(),
        meta=None,
        doc_id=explicit_id,
    )


@pytest.mark.asyncio
async def test_run_pipeline_marks_error_when_no_parent_chunks(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> None:
    created_id = uuid.uuid4()
    document_service_mock.create_doc.return_value = created_id
    ingestion_service._chunker = MagicMock()
    ingestion_service._chunker.process.return_value = ([], [{"text": "child", "parent_id": uuid.uuid4()}])

    with pytest.raises(ValueError, match="No parent chunks produced"):
        await ingestion_service._run_pipeline(
            file_path="file.pdf",
            filename="file.pdf",
            file_hash="hash",
            doc_id=None,
            meta=None,
        )

    document_service_mock.add_parent_chunks.assert_not_called()
    vector_indexing_service_mock.upsert_points.assert_not_called()
    document_service_mock.set_status.assert_awaited_once_with(created_id, DocumentStatus.error)


@pytest.mark.asyncio
async def test_run_pipeline_marks_error_when_no_child_chunks(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> None:
    created_id = uuid.uuid4()
    document_service_mock.create_doc.return_value = created_id
    ingestion_service._chunker = MagicMock()
    ingestion_service._chunker.process.return_value = ([{"id": uuid.uuid4(), "text": "parent"}], [])

    with pytest.raises(ValueError, match="No child chunks produced"):
        await ingestion_service._run_pipeline(
            file_path="file.pdf",
            filename="file.pdf",
            file_hash="hash",
            doc_id=None,
            meta=None,
        )

    document_service_mock.add_parent_chunks.assert_not_called()
    vector_indexing_service_mock.upsert_points.assert_not_called()
    document_service_mock.set_status.assert_awaited_once_with(created_id, DocumentStatus.error)


@pytest.mark.asyncio
async def test_run_pipeline_marks_error_when_vector_upsert_fails(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> None:
    created_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    document_service_mock.create_doc.return_value = created_id
    vector_indexing_service_mock.upsert_points.side_effect = RuntimeError("vector failed")
    ingestion_service._chunker = MagicMock()
    ingestion_service._chunker.process.return_value = (
        [{"id": parent_id, "text": "parent"}],
        [{"text": "child", "parent_id": parent_id}],
    )

    with pytest.raises(RuntimeError, match="vector failed"):
        await ingestion_service._run_pipeline(
            file_path="file.pdf",
            filename="file.pdf",
            file_hash="hash",
            doc_id=None,
            meta=None,
        )

    document_service_mock.add_parent_chunks.assert_awaited_once_with(created_id, [{"id": parent_id, "text": "parent"}])
    document_service_mock.set_status.assert_awaited_once_with(created_id, DocumentStatus.error)


@pytest.mark.asyncio
async def test_run_pipeline_does_not_mark_error_if_create_doc_fails(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
) -> None:
    document_service_mock.create_doc.side_effect = RuntimeError("create failed")

    with pytest.raises(RuntimeError, match="create failed"):
        await ingestion_service._run_pipeline(
            file_path="file.pdf",
            filename="file.pdf",
            file_hash="hash",
            doc_id=None,
            meta=None,
        )

    vector_indexing_service_mock.upsert_points.assert_not_called()
    document_service_mock.set_status.assert_not_called()
