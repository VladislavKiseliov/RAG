from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str



class SearchRequest(BaseModel):
    """Incoming search query payload."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    doc_id: str | None = None
    score_threshold: float | None = None


class SourceItem(BaseModel):
    """One source parent chunk returned by retriever."""

    parent_id: str
    page_num: str
    headers: dict
    text: str
    score: float


class SearchResponse(BaseModel):
    """Search response with generated answer and evidence sources."""

    answer: str
    sources: list[SourceItem]