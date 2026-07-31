from __future__ import annotations

import httpx


class TeiSyncEmbedder:
    """Синхронный клиент TEI для ML-роутера.

    MLQueryRouter.route() — синхронный CPU-bound метод, вызывается из
    lean_rag_agent.py через asyncio.to_thread, поэтому блокирующий httpx.Client
    здесь безопасен (тот же поток и так занят до возврата predict_proba).

    Без "query: "/"passage: " префикса — ml_router/train.py эмбеддит сырой текст
    без префикса, сохраняем то же поведение при инференсе (иначе классификатор
    увидит другое распределение векторов, чем при обучении).
    """

    def __init__(self, *, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/embed",
                json={"inputs": texts, "normalize": normalize_embeddings},
            )
        response.raise_for_status()
        return response.json()