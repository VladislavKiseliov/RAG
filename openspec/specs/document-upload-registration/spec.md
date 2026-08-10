## Purpose
Registers a new document and issues a presigned MinIO PUT URL before any content exists.

## Requirements

### Requirement: Pre-emptive duplicate filename rejection
The system MUST reject a new upload registration if a document with the same filename already exists, before issuing an upload URL.

#### Scenario: Uploading a filename already in the catalog
- **WHEN** a client requests an upload link for a filename that already exists
- **THEN** the request is rejected and no presigned URL is issued

### Requirement: Extension and size validated before upload URL is issued
The system MUST validate the file extension against an allow-list and reject sizes above the configured maximum before creating the document record.

#### Scenario: Requesting an upload link for a disallowed extension
- **WHEN** a client requests an upload link for a file extension outside `.pdf/.docx/.txt`
- **THEN** the request is rejected without creating a document row or presigned URL

### Requirement: Filename sanitization in storage key
The generated S3 key MUST be built from a sanitized filename (no path traversal, no null bytes) combined with a UUIDv7 document id.

#### Scenario: Filename contains path-traversal characters
- **WHEN** a client requests an upload link with a filename containing `../` sequences
- **THEN** the resulting storage key uses a sanitized version of the filename, not the raw traversal path
