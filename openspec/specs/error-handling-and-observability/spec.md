## Purpose
Cross-cutting typed exception hierarchy mapped to HTTP responses, plus Prometheus metrics, for rag_service.

## Requirements

### Requirement: Layered typed error hierarchy
Domain errors MUST be raised as subclasses of a common `AppError` hierarchy (`PostgresError`/`StorageError`/`VectorStoreError`), each carrying its own HTTP status.

#### Scenario: A vector-store operation fails
- **WHEN** a Qdrant operation raises an error
- **THEN** it is wrapped as a `VectorStoreError` subclass carrying an appropriate HTTP status, not a raw driver exception

### Requirement: No internal detail leakage for storage failures
Internal error details from storage/vector-store failures MUST NOT be included in client-facing responses; they are logged server-side only.

#### Scenario: An S3 operation fails with an internal error message
- **WHEN** a storage error occurs
- **THEN** the client receives a generic error message; the internal detail is only in the server log

### Requirement: Catch-all fallback for unclassified exceptions
Any exception not matching a known typed error MUST be caught by a generic handler returning a generic 500.

#### Scenario: An unexpected exception type is raised
- **WHEN** an exception occurs that isn't a subclass of any known `AppError` type
- **THEN** the client receives a generic 500 response rather than an unhandled server crash
