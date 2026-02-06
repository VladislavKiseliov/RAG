from fastapi.testclient import TestClient

from app.main import app
import app.api.routes as routes


client = TestClient(app)


class _DummyAsyncResult:
    def __init__(self, job_id: str, app=None, state: str = "PENDING", result=None, info=None):
        self.state = state
        self.result = result
        self.info = info


def test_ingest_file_success(tmp_path, monkeypatch):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%")

    class _DummyTask:
        id = "job-1"

    monkeypatch.setattr(routes.ingest_pdf_task, "delay", lambda *args, **kwargs: _DummyTask())
    monkeypatch.setattr(routes, "add_job", lambda *args, **kwargs: None)

    response = client.post(
        "/ingest",
        json={"path": str(pdf_path), "collection": "test_collection", "metadata": {"a": 1}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["job_ids"] == ["job-1"]


def test_ingest_dir_no_pdf(tmp_path, monkeypatch):
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(routes, "add_job", lambda *args, **kwargs: None)

    response = client.post("/ingest", json={"path": str(tmp_path), "collection": "test_collection"})
    assert response.status_code == 400


def test_ingest_path_not_exists():
    response = client.post("/ingest", json={"path": "Z:/does/not/exist", "collection": "test_collection"})
    assert response.status_code == 404


def test_list_jobs(monkeypatch):
    job_ids = ["job-a", "job-b"]

    def _dummy_async_result(job_id: str, app=None):
        if job_id == "job-a":
            return _DummyAsyncResult(job_id, state="SUCCESS", result={"ok": True})
        return _DummyAsyncResult(job_id, state="STARTED")

    monkeypatch.setattr(routes, "AsyncResult", _dummy_async_result)
    monkeypatch.setattr(routes, "list_job_ids", lambda limit=100, offset=0: job_ids)
    monkeypatch.setattr(routes, "count_jobs", lambda: 2)
    monkeypatch.setattr(
        routes,
        "get_job",
        lambda job_id: {
            "file_path": f"/data/docs/{job_id}.pdf",
            "collection": "test_collection",
            "created_at": "2026-01-30T00:00:00+00:00",
        },
    )

    response = client.get("/jobs?limit=10&offset=0")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["status"] in {"done", "processing"}


def test_job_status_done(monkeypatch):
    monkeypatch.setattr(
        routes,
        "AsyncResult",
        lambda job_id, app=None: _DummyAsyncResult(job_id, state="SUCCESS", result={"count": 1}),
    )

    response = client.get("/jobs/job-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["stats"] == {"count": 1}
