from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_service.api.rag_routes import router


class FakeRetrieveService:
    def __init__(self):
        self.called_with = None

    async def search(self, *, query: str, top_k: int):
        self.called_with = {
            "query": query,
            "top_k": top_k,
        }
        return {
            "query": query,
            "items": [
                {
                    "doc_id": "doc-1",
                    "parent_id": "parent-1",
                    "page_num": "1",
                    "score": 0.91,
                    "text": "test chunk",
                    "headers": {"H1": "Intro"},
                }
            ],
            "total": 1,
        }


def test_retrieve_returns_200_and_expected_response():
    app = FastAPI()
    app.include_router(router)

    fake_service = FakeRetrieveService()
    app.state.search_service = fake_service

    client = TestClient(app)

    response = client.post(
        "/documents/retrieve",
        json={
            "query": "test query",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "test query",
        "items": [
            {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "page_num": "1",
                "score": 0.91,
                "text": "test chunk",
                "headers": {"H1": "Intro"},
            }
        ],
        "total": 1,
    }
    assert fake_service.called_with == {
        "query": "test query",
        "top_k": 3,
    }
