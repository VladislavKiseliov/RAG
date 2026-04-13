from __future__ import annotations

import httpx


class RagClient:
    def __init__(self, *, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout

    async def retrieve(self, *, query: str, doc_id: str | None) -> dict:
        payload = {"query": query}
        if doc_id is not None:
            payload["doc_id"] = doc_id

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/documents/retrieve", json=payload)

        response.raise_for_status()
        return response.json()
