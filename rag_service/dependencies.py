from fastapi import Request, Depends

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import Annotated

from rag_service.application.document_service import DataBaseDocumentService, DocumentQueryService
from rag_service.application.document_upload_service import  DocumentOrchestrator

from backend.infrastructure import BackendContainer
from rag_service.application.retrieve_service import RetrieveService
from rag_service.application.task_dispatcher_service import TaskDispatcherService
from rag_service.infrastructure import RagContainer
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider


def get_container(request: Request) -> BackendContainer:
    return request.app.state.container


def get_session_factory(container: RagContainer = Depends(get_container)):
    return container.session_factory

def get_s3_storage(container: RagContainer = Depends(get_container)):
    return container.s3_storage

def get_vector_storage(container: RagContainer = Depends(get_container)):
    return container.vector_storage

VectorStorageDep = Annotated[VectorStorageProvider, Depends(get_vector_storage)]
S3StorageDep = Annotated[S3StorageProvider, Depends(get_s3_storage)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]

# 2. Функция-зависимость для получения сервиса
async def get_db_doc_service(session_factory : SessionFactoryDep)->DataBaseDocumentService:
    return DataBaseDocumentService(session_factory)

DocServiceDep = Annotated[DataBaseDocumentService, Depends(get_db_doc_service)]

async def get_db_query_service(session_factory : SessionFactoryDep)->DocumentQueryService:
    return DocumentQueryService(session_factory)

DocQueryServiceDep = Annotated[DocumentQueryService, Depends(get_db_query_service)]


async def get_retrieval_service(vector_storage:VectorStorageDep,
                                database:DocQueryServiceDep,
):
    return RetrieveService(vector_storage=vector_storage,
                           database =database
    )

RetrieveServiceDep = Annotated[RetrieveService, Depends(get_retrieval_service)]

async def get_task_dispatcher_service():
    return TaskDispatcherService()


TaskDispatcherServiceDep = Annotated[TaskDispatcherService, Depends(get_task_dispatcher_service)]



async def get_document_management_service(
    db_doc_service: DocServiceDep,
    s3_storage: S3StorageDep,
    vector_storage: VectorStorageDep
) -> DocumentOrchestrator:
    return DocumentOrchestrator(
        s3_storage=s3_storage,
        vector_storage=vector_storage,
        database=db_doc_service
    )
RAGServiceDep = Annotated[DocumentOrchestrator, Depends(get_document_management_service)]


