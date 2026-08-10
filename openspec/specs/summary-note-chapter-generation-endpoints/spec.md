## Purpose
Auxiliary single-shot generation endpoints (conversation summary, note generation, chapter/document/table summaries) used by backend and rag_service.

## Requirements

### Requirement: Cheap model tier for high-volume ingestion summaries
Chapter, document, and table summary generation MUST use the `llm_summary` (cheap) model tier, since these are high-volume best-effort calls invoked per-document during ingestion.

#### Scenario: rag_service requests a chapter summary during ingestion
- **WHEN** `/llm/chapter-summary` is called
- **THEN** the cheap `llm_summary` model tier is used, not the main conversational model

### Requirement: Conversation summary and note generation use the main tier
Conversation summarization and note generation MUST use the main `llm` model tier, since they're user-facing and lower volume.

#### Scenario: A conversation crosses the summarization threshold
- **WHEN** `/llm/summary` is called for a chat's rolling summary
- **THEN** the main model tier is used

### Requirement: Note generation has a constrained output vocabulary with fallback parsing
Note generation MUST constrain tags/folders to an allowed vocabulary and fall back to a plaintext parse if the LLM doesn't return valid JSON.

#### Scenario: The note-generation LLM call returns non-JSON text
- **WHEN** the LLM response for `/llm/note` isn't valid JSON
- **THEN** a plaintext-fallback parser extracts a usable note instead of failing the request
