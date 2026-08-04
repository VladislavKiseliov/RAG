from typing import Annotated
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.container import RagContainer
from rag_service.application.abbreviation_expander import AbbreviationExpander
from rag_service.application.document_service import DataBaseDocumentService, DocumentQueryService
from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.application.retrieve_service import RetrieveService
from rag_service.application.task_dispatcher_service import TaskDispatcherService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider

# --- 1. Базовые зависимости контейнера ---

def get_container(request: Request) -> RagContainer:
    """Извлекает инфраструктурный контейнер из состояния приложения."""
    return request.app.state.container

def get_session_factory(container: RagContainer = Depends(get_container)):
    return container.session_factory

def get_s3_storage(container: RagContainer = Depends(get_container)):
    return container.s3_storage

def get_vector_storage(container: RagContainer = Depends(get_container)):
    return container.vector_storage

def get_notes_vector_storage(container: RagContainer = Depends(get_container)):
    return container.notes_vector_storage

def get_v_indexing_service(container: RagContainer = Depends(get_container)):
    return container.v_indexing_service

def get_abbreviation_expander(container: RagContainer = Depends(get_container)):
    return container.abbreviation_expander

# --- 2. Annotated Типы для чистого кода в роутах ---

ContainerDep = Annotated[RagContainer, Depends(get_container)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
S3StorageDep = Annotated[BucketStorageProvider, Depends(get_s3_storage)]
VectorStorageDep = Annotated[VectorStorageProvider, Depends(get_vector_storage)]
NotesVectorStorageDep = Annotated[VectorStorageProvider, Depends(get_notes_vector_storage)]
VectorIndexingDep = Annotated[VectorIndexingService, Depends(get_v_indexing_service)]
AbbreviationExpanderDep = Annotated[AbbreviationExpander, Depends(get_abbreviation_expander)]

# --- 3. Функции-фабрики для доменных сервисов ---

async def get_db_doc_service(session_factory: SessionFactoryDep) -> DataBaseDocumentService:
    """Сервис для изменения данных (Commands)."""
    return DataBaseDocumentService(session_factory)

async def get_db_query_service(session_factory: SessionFactoryDep) -> DocumentQueryService:
    """Сервис для чтения данных (Queries)."""
    return DocumentQueryService(session_factory)

async def get_retrieval_service(
    vector_storage: VectorStorageDep,
    database: Annotated[DocumentQueryService, Depends(get_db_query_service)],
    v_indexing: VectorIndexingDep,
    s3_storage: S3StorageDep,
    abbreviation_expander: AbbreviationExpanderDep,
) -> RetrieveService:
    """Сервис поиска (Retrieval Pipeline)."""
    return RetrieveService(
        vector_storage=vector_storage,
        database=database,
        v_indexing_service=v_indexing,
        s3_storage=s3_storage,
        abbreviation_expander=abbreviation_expander,
    )

async def get_task_dispatcher_service(db_doc_service: Annotated[DataBaseDocumentService, Depends(get_db_doc_service)]) -> TaskDispatcherService:
    """Сервис постановки задач в Celery."""
    return TaskDispatcherService(database=db_doc_service)

async def get_document_orchestrator(
    db_doc_service: Annotated[DataBaseDocumentService, Depends(get_db_doc_service)],
    s3_storage: S3StorageDep,
    vector_storage: VectorStorageDep
) -> DocumentOrchestrator:
    """Оркестратор управления документами (Upload/Delete/List)."""
    return DocumentOrchestrator(
        s3_storage=s3_storage,
        vector_storage=vector_storage,
        database=db_doc_service
    )

# --- 4. Финальные зависимости для инъекции в роуты ---

DocServiceDep = Annotated[DataBaseDocumentService, Depends(get_db_doc_service)]
DocQueryServiceDep = Annotated[DocumentQueryService, Depends(get_db_query_service)]
RetrieveServiceDep = Annotated[RetrieveService, Depends(get_retrieval_service)]
TaskDispatcherServiceDep = Annotated[TaskDispatcherService, Depends(get_task_dispatcher_service)]
DocumentOrchestratorDep = Annotated[DocumentOrchestrator, Depends(get_document_orchestrator)]