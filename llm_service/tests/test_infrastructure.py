from __future__ import annotations

from unittest.mock import patch

from llm_service.infrastructure import _build_query_router


def test_query_router_build_failure_is_not_fatal():
    # B4: route_node (единственный вызывающий .route()) отключён от живого графа -
    # раньше сбой здесь (битый/отсутствующий intent_model.pkl, несовместимая версия
    # joblib/sklearn) валил build_container() целиком, и сервис не поднимался вообще
    # из-за компонента, который по факту мёртв.
    with patch("joblib.load", side_effect=FileNotFoundError("model file missing")):
        result = _build_query_router()
    assert result is None


def test_query_router_builds_normally_when_artifact_is_fine():
    with patch("joblib.load", return_value="fake-classifier"), \
         patch("llm_service.ml_router.tei_embedder.TeiSyncEmbedder"), \
         patch("llm_service.ml_router.router.MLQueryRouter") as mock_router_cls:
        mock_router_cls.return_value = "fake-router-instance"
        result = _build_query_router()
    assert result == "fake-router-instance"
