import uuid

import pytest

from rag_service.application.retrieve_service import RetrieveService


class FakeVectorProvider:
    async def search(self, query, top_k=5, doc_id=None, score_threshold=None):
        return []



class FakeDocumentQueryService:
    async def get_parent_chunks(self,requested_parent_ids: list[str],doc_id: uuid.UUID | None = None,
    ):
            return []


@pytest.mark.asyncio
async def test_retrieve_service_empty_request_returns_empty_response():
    retrieve_service = RetrieveService(
        session_factory=None,
        vector_provider=FakeVectorProvider(),
    )

    result = await retrieve_service.search(query="")

    assert result == {
        "query": "",
        "items": [],
        "total": 0,
    }
