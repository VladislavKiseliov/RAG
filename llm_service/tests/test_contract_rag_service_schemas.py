"""Контрактный тест: RetrieveItem/RetrieveItemMetadata/ChildChunk не должны разойтись
между rag_service/api/schemas.py (источник) и llm_service/application/lean_rag_models.py
(независимая копия для агента). Pydantic по умолчанию тихо отбрасывает незнакомые поля
(extra="ignore") - расхождение не даст ошибки при валидации, просто новое поле не доедет
до агента. Парсим rag_service/api/schemas.py статически через ast, не импортом - у
rag_service свои зависимости (SQLAlchemy, Docling и т.д.), не установленные в
llm_service/.venv."""

from __future__ import annotations

import ast
from pathlib import Path

from llm_service.application.lean_rag_models import ChildChunk, RetrieveItem, RetrieveItemMetadata

_RAG_SERVICE_SCHEMAS = Path(__file__).resolve().parents[2] / "rag_service" / "api" / "schemas.py"


def _rag_service_field_names(class_name: str) -> set[str]:
    tree = ast.parse(_RAG_SERVICE_SCHEMAS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    raise AssertionError(f"{class_name} not found in {_RAG_SERVICE_SCHEMAS}")


def test_retrieve_item_metadata_matches_rag_service():
    assert set(RetrieveItemMetadata.model_fields) == _rag_service_field_names("RetrieveItemMetadata")


def test_retrieve_item_matches_rag_service():
    assert set(RetrieveItem.model_fields) == _rag_service_field_names("RetrieveItem")


def test_child_chunk_matches_rag_service():
    assert set(ChildChunk.model_fields) == _rag_service_field_names("ChildChunk")
