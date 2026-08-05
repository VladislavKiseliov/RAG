import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_service.application.ingestion_service import IngestionResult, IngestionService
from rag_service.domain.chunking.docling_models import Chapter, ParsedDocument
from rag_service.domain.errors.storage import StorageReadError
from rag_service.domain.models.vector_point import SparseVectorValue
from rag_service.models import DocumentStatus

CHAPTER_TEXT = (
    "Общие положения. Настоящий раздел устанавливает порядок допуска персонала "
    "к эксплуатации оборудования и правила обращения с инструментом на объекте."
)


def _db_doc(doc_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=doc_id, filename="manual.pdf", s3key="key.pdf", file_size=9)


@pytest.fixture
def document_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_document_by_hash.return_value = None
    return mock


@pytest.fixture
def vector_storage_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def vector_indexing_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_hybrid_vectors.return_value = ([[0.1, 0.2]], [SparseVectorValue(indices=[1], values=[0.5])])
    return mock


@pytest.fixture
def s3_storage_mock() -> AsyncMock:
    mock = AsyncMock()
    # A20: validate_file_content() теперь проверяет магические байты против
    # заявленного расширения (.pdf для всех тестовых документов этого файла).
    mock.get_file.return_value = b"%PDF-1.4 fake pdf bytes"
    return mock


@pytest.fixture
def conversion_pipeline_mock() -> MagicMock:
    mock = MagicMock()
    mock.convert_document.return_value = ParsedDocument(
        full_markdown="full text",
        chapters=[Chapter(number="1", title="Общие положения", markdown=CHAPTER_TEXT)],
        page_count=3,
    )
    return mock


@pytest.fixture
def ingestion_service(
    document_service_mock: AsyncMock,
    vector_storage_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
    s3_storage_mock: AsyncMock,
    conversion_pipeline_mock: MagicMock,
) -> IngestionService:
    return IngestionService(
        document_service=document_service_mock,
        vector_storage=vector_storage_mock,
        vector_indexing_service=vector_indexing_service_mock,
        s3_storage=s3_storage_mock,
        conversion_pipeline=conversion_pipeline_mock,
    )


@pytest.mark.asyncio
async def test_process_document_returns_error_when_document_row_missing(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    s3_storage_mock: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    document_service_mock.get_document_by_id.return_value = None

    result = await ingestion_service.process_document(doc_id, "key.pdf")

    assert result == IngestionResult(doc_id, DocumentStatus.ERROR)
    s3_storage_mock.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_process_document_happy_path_completes_and_indexes(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    vector_storage_mock: AsyncMock,
    vector_indexing_service_mock: AsyncMock,
    s3_storage_mock: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    document_service_mock.get_document_by_id.return_value = _db_doc(doc_id)

    result = await ingestion_service.process_document(doc_id, "key.pdf")

    assert result == IngestionResult(doc_id, DocumentStatus.COMPLETED)
    s3_storage_mock.get_file.assert_awaited_once_with("key.pdf")

    document_service_mock.add_parent_chunks.assert_awaited_once()
    parent_chunks = document_service_mock.add_parent_chunks.await_args.args[1]
    assert len(parent_chunks) == 1

    vector_storage_mock.delete_by_field.assert_awaited_once_with("doc_id", str(doc_id))
    vector_storage_mock.upsert_vectors.assert_awaited_once()
    points = vector_storage_mock.upsert_vectors.await_args.args[0]
    assert len(points) == 1
    assert points[0].payload["doc_id"] == str(doc_id)

    final_update = document_service_mock.update_document.await_args_list[-1]
    assert final_update.kwargs["update_data"]["status"] == DocumentStatus.COMPLETED
    assert final_update.kwargs["update_data"]["chunk_count"] == 1


@pytest.mark.asyncio
async def test_process_document_handles_duplicate_file(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    s3_storage_mock: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    document_service_mock.get_document_by_id.return_value = _db_doc(doc_id)
    document_service_mock.get_document_by_hash.return_value = SimpleNamespace(id=uuid.uuid4())

    result = await ingestion_service.process_document(doc_id, "key.pdf")

    assert result == IngestionResult(doc_id, DocumentStatus.DUPLICATE)
    document_service_mock.delete_document.assert_awaited_once_with(doc_id)
    s3_storage_mock.delete_file.assert_awaited_once_with("key.pdf")


@pytest.mark.asyncio
async def test_process_document_reraises_transient_storage_error_for_celery_retry(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    s3_storage_mock: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    document_service_mock.get_document_by_id.return_value = _db_doc(doc_id)
    s3_storage_mock.get_file.side_effect = StorageReadError("boom")

    with pytest.raises(StorageReadError):
        await ingestion_service.process_document(doc_id, "key.pdf")

    # Транзиентная инфраструктурная ошибка не помечает документ ERROR/DUPLICATE —
    # статус остаётся PROCESSING, чтобы Celery мог ретраить с того же места.
    last_update = document_service_mock.update_document.await_args_list[-1]
    assert last_update.kwargs["update_data"]["status"] == DocumentStatus.PROCESSING


@pytest.mark.asyncio
async def test_process_document_marks_error_when_extraction_yields_no_chapters(
    ingestion_service: IngestionService,
    document_service_mock: AsyncMock,
    conversion_pipeline_mock: MagicMock,
) -> None:
    doc_id = uuid.uuid4()
    document_service_mock.get_document_by_id.return_value = _db_doc(doc_id)
    conversion_pipeline_mock.convert_document.return_value = ParsedDocument(full_markdown="", chapters=[])

    result = await ingestion_service.process_document(doc_id, "key.pdf")

    assert result == IngestionResult(doc_id, DocumentStatus.ERROR)
    last_update = document_service_mock.update_document.await_args_list[-1]
    assert last_update.kwargs["update_data"]["status"] == DocumentStatus.ERROR
