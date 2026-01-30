from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query

from ..schemas import IngestRequest, IngestResponse, JobStatus, JobItem, JobsListResponse
from ..services.job_store import add_job, count_jobs, get_job, list_job_ids
from ..tasks import celery_app, ingest_pdf_task


router = APIRouter()

def _map_state(state: str) -> str:
    if state == "PENDING":
        return "pending"
    if state == "STARTED":
        return "processing"
    if state == "FAILURE":
        return "failed"
    if state == "SUCCESS":
        return "done"
    if state == "RETRY":
        return "retry"
    if state == "REVOKED":
        return "revoked"
    if state == "RECEIVED":
        return "received"
    if state == "QUEUED":
        return "queued"
    return "unknown"


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    """Queue PDF ingestion tasks for a file or all PDFs in a directory."""
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")

    job_ids: list[str] = []
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        task = ingest_pdf_task.delay(str(path), request.collection, request.metadata)
        add_job(task.id, str(path), request.collection, request.metadata)
        job_ids.append(task.id)
    else:
        for file_path in path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == ".pdf":
                task = ingest_pdf_task.delay(str(file_path), request.collection, request.metadata)
                add_job(task.id, str(file_path), request.collection, request.metadata)
                job_ids.append(task.id)

    if not job_ids:
        raise HTTPException(status_code=400, detail="No PDF files found")

    return IngestResponse(job_ids=job_ids, total=len(job_ids))


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    """Return the current status (and result if available) for a single job."""
    result = AsyncResult(job_id, app=celery_app)
    if result.state == "PENDING":
        return JobStatus(status="pending")
    if result.state == "STARTED":
        return JobStatus(status="processing")
    if result.state == "FAILURE":
        return JobStatus(status="failed", error=str(result.info))
    if result.state == "SUCCESS":
        return JobStatus(status="done", stats=result.result)
    return JobStatus(status=_map_state(result.state))


@router.get("/jobs", response_model=JobsListResponse)
def list_jobs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JobsListResponse:
    """List queued/known jobs with pagination."""
    job_ids = list_job_ids(limit=limit, offset=offset)
    items: list[JobItem] = []
    for job_id in job_ids:
        result = AsyncResult(job_id, app=celery_app)
        status = _map_state(result.state)

        stored = get_job(job_id) or {}
        items.append(
            JobItem(
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                file_path=stored.get("file_path"),
                collection=stored.get("collection"),
                created_at=stored.get("created_at"),
            )
        )

    return JobsListResponse(total=count_jobs(), items=items)
