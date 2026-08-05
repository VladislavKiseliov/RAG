"""get_stream_writer() (langgraph.config) кидает RuntimeError вне запущенного графа -
ноды графа вызываются и через agent.app.ainvoke()/astream() (там всё ок, вне custom
stream_mode LangGraph сам подставляет no-op writer), и напрямую в юнит-тестах
(agent.nodes.plan_node(state) и т.п., без графа вообще) - там get_stream_writer()
падает. Обёртка нужна нодам, которые должны работать в обоих случаях."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.config import get_stream_writer


def get_safe_stream_writer() -> Callable[[Any], None]:
    try:
        return get_stream_writer()
    except RuntimeError:
        return lambda _: None
