from __future__ import annotations

from fastapi import Request

from llm_service.application.lean_rag_agent import LeanRagAgent


def get_lean_rag_agent(request: Request) -> LeanRagAgent:
    return request.app.state.container.agent