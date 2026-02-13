from pathlib import Path
import os

from fastapi import APIRouter, HTTPException, Query
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import GEMINI_API_KEY, LLM_MODEL_NAME
from ..services.rag_service import _extract_answer


from ..schemas import (
    IngestRequest,
    IngestResponse,
    JobStatus,
    JobItem,
    JobsListResponse,
    RagQueryRequest,
    RagAnswerResponse,
)
from ..services.job_store import add_job, count_jobs, get_job, list_job_ids


router = APIRouter()
_llm_client: ChatGoogleGenerativeAI | None = None


def _get_llm_client() -> ChatGoogleGenerativeAI:
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    # api_key = os.getenv("GEMINI_API_KEY")
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    _llm_client = ChatGoogleGenerativeAI(model=LLM_MODEL_NAME, google_api_key=api_key)
    return _llm_client


# def _extract_answer(content) -> str:
#     if isinstance(content, str):
#         return content
#     if isinstance(content, list):
#         parts: list[str] = []
#         for item in content:
#             if isinstance(item, str):
#                 parts.append(item)
#                 continue
#             if isinstance(item, dict):
#                 text = item.get("text")
#                 if isinstance(text, str):
#                     parts.append(text)
#         return "\n".join(part for part in parts if part).strip()
#     return str(content) if content is not None else ""
#
#
# def _get_celery_runtime():
#     """Lazy import to allow running /rag/answer without Celery runtime on startup."""
#     try:
#         from ..tasks import celery_app, ingest_pdf_task  # local import by design
#         return celery_app, ingest_pdf_task
#     except Exception as exc:
#         raise HTTPException(status_code=503, detail=f"Celery runtime is unavailable: {exc}")
#
# def _map_state(state: str) -> str:
#     if state == "PENDING":
#         return "pending"
#     if state == "STARTED":
#         return "processing"
#     if state == "FAILURE":
#         return "failed"
#     if state == "SUCCESS":
#         return "done"
#     if state == "RETRY":
#         return "retry"
#     if state == "REVOKED":
#         return "revoked"
#     if state == "RECEIVED":
#         return "received"
#     if state == "QUEUED":
#         return "queued"
#     return "unknown"
#
#
# @router.post("/ingest", response_model=IngestResponse)
# def ingest(request: IngestRequest) -> IngestResponse:
#     """Queue PDF ingestion tasks for a file or all PDFs in a directory."""
#     celery_app, ingest_pdf_task = _get_celery_runtime()
#     path = Path(request.path)
#     if not path.exists():
#         raise HTTPException(status_code=404, detail="Path does not exist")
#
#     job_ids: list[str] = []
#     if path.is_file():
#         if path.suffix.lower() != ".pdf":
#             raise HTTPException(status_code=400, detail="Only PDF files are supported")
#         task = ingest_pdf_task.delay(str(path), request.collection, request.metadata)
#         add_job(task.id, str(path), request.collection, request.metadata)
#         job_ids.append(task.id)
#     else:
#         for file_path in path.iterdir():
#             if file_path.is_file() and file_path.suffix.lower() == ".pdf":
#                 task = ingest_pdf_task.delay(str(file_path), request.collection, request.metadata)
#                 add_job(task.id, str(file_path), request.collection, request.metadata)
#                 job_ids.append(task.id)
#
#     if not job_ids:
#         raise HTTPException(status_code=400, detail="No PDF files found")
#
#     return IngestResponse(job_ids=job_ids, total=len(job_ids))
#
#
# @router.get("/jobs/{job_id}", response_model=JobStatus)
# def job_status(job_id: str) -> JobStatus:
#     """Return the current status (and result if available) for a single job."""
#     from celery.result import AsyncResult
#
#     celery_app, _ = _get_celery_runtime()
#     result = AsyncResult(job_id, app=celery_app)
#     if result.state == "PENDING":
#         return JobStatus(status="pending")
#     if result.state == "STARTED":
#         return JobStatus(status="processing")
#     if result.state == "FAILURE":
#         return JobStatus(status="failed", error=str(result.info))
#     if result.state == "SUCCESS":
#         return JobStatus(status="done", stats=result.result)
#     return JobStatus(status=_map_state(result.state))
#
#
# @router.get("/jobs", response_model=JobsListResponse)
# def list_jobs(
#     limit: int = Query(100, ge=1, le=1000),
#     offset: int = Query(0, ge=0),
# ) -> JobsListResponse:
#     """List queued/known jobs with pagination."""
#     from celery.result import AsyncResult
#
#     celery_app, _ = _get_celery_runtime()
#     job_ids = list_job_ids(limit=limit, offset=offset)
#     items: list[JobItem] = []
#     for job_id in job_ids:
#         result = AsyncResult(job_id, app=celery_app)
#         status = _map_state(result.state)
#
#         stored = get_job(job_id) or {}
#         items.append(
#             JobItem(
#                 job_id=job_id,
#                 status=status,  # type: ignore[arg-type]
#                 file_path=stored.get("file_path"),
#                 collection=stored.get("collection"),
#                 created_at=stored.get("created_at"),
#             )
#         )
#
#     return JobsListResponse(total=count_jobs(), items=items)
#

@router.post("/rag/answer", response_model=RagAnswerResponse)
def rag_answer(request: RagQueryRequest) -> RagAnswerResponse:
    """Answer a question directly via LLM API (without retrieval)."""
    try:
        if not request.question or not request.question.strip():
            raise HTTPException(status_code=400, detail="Question is required")
        print(f"{request.question=}")
        response = _get_llm_client().invoke(request.question)
        answer = _extract_answer(getattr(response, "content", ""))
        return RagAnswerResponse(
            answer=answer,
            sources=[],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
