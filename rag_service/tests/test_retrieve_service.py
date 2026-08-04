"""RetrieveService.retrieve(): проверка единственной новой точки интеграции A11 -
AbbreviationExpander.expand() вызывается первым шагом, и результат расширения
(а не исходный список queries) определяет, идёт ли запрос через search() или
batch_search(). Остальной pipeline (dedup/parent-hydration/table-resolution)
уже покрыт живыми e2e-проверками, здесь не дублируется.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_service.application.abbreviation_expander import AbbreviationExpander
from rag_service.application.retrieve_service import RetrieveService


@pytest.fixture
def vector_storage_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    mock.batch_search = AsyncMock(return_value=[[], []])
    return mock


@pytest.fixture
def v_indexing_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_query_embedding = AsyncMock(return_value=[0.1])
    mock.get_embeddings = AsyncMock(return_value=[[0.1], [0.2]])
    return mock


def _make_service(vector_storage, v_indexing_service, abbreviation_expander) -> RetrieveService:
    return RetrieveService(
        vector_storage=vector_storage,
        database=AsyncMock(),
        v_indexing_service=v_indexing_service,
        s3_storage=AsyncMock(),
        abbreviation_expander=abbreviation_expander,
    )


@pytest.mark.asyncio
async def test_retrieve_calls_expander_and_uses_search_when_unexpanded(
    vector_storage_mock: AsyncMock, v_indexing_service_mock: AsyncMock
) -> None:
    expander = MagicMock()
    expander.expand = MagicMock(return_value=["обычный запрос"])
    service = _make_service(vector_storage_mock, v_indexing_service_mock, expander)

    await service.retrieve(queries=["обычный запрос"], top_k=5)

    expander.expand.assert_called_once_with(["обычный запрос"])
    vector_storage_mock.search.assert_awaited_once()
    vector_storage_mock.batch_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_uses_batch_search_when_expander_adds_a_variant(
    vector_storage_mock: AsyncMock, v_indexing_service_mock: AsyncMock
) -> None:
    expander = MagicMock()
    expander.expand = MagicMock(
        return_value=["сроки ПНР", "сроки ПНР (пусконаладочные работы)"]
    )
    service = _make_service(vector_storage_mock, v_indexing_service_mock, expander)

    await service.retrieve(queries=["сроки ПНР"], top_k=5)

    vector_storage_mock.batch_search.assert_awaited_once()
    vector_storage_mock.search.assert_not_awaited()
    call_kwargs = vector_storage_mock.batch_search.await_args.kwargs
    assert call_kwargs["query_texts"] == ["сроки ПНР", "сроки ПНР (пусконаладочные работы)"]


@pytest.mark.asyncio
async def test_retrieve_end_to_end_with_real_abbreviation_expander(
    vector_storage_mock: AsyncMock, v_indexing_service_mock: AsyncMock
) -> None:
    """Не мок AbbreviationExpander, а реальный экземпляр - проверяет, что
    RetrieveService действительно интегрирован с настоящей логикой expand(),
    не только с её мок-заменой."""
    expander = AbbreviationExpander.from_pairs([("ПНР", "пусконаладочные работы")])
    service = _make_service(vector_storage_mock, v_indexing_service_mock, expander)

    await service.retrieve(queries=["сроки проведения ПНР"], top_k=5)

    vector_storage_mock.batch_search.assert_awaited_once()
    call_kwargs = vector_storage_mock.batch_search.await_args.kwargs
    assert call_kwargs["query_texts"] == [
        "сроки проведения ПНР",
        "сроки проведения ПНР (пусконаладочные работы)",
    ]
