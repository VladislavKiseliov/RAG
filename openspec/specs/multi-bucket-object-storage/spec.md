## Purpose
Domain-segmented S3/MinIO storage abstraction (knowledge-base, users, projects buckets) with presigned URL generation. Currently, only the knowledge-base bucket is wired into the running application; the users/projects storage services exist with full method parity but are not instantiated anywhere.

## Requirements

### Requirement: Separate internal vs public endpoints
Storage operations MUST use a private (internal, service-to-service) MinIO endpoint for direct access and a separate public endpoint for presigned URLs handed to browsers.

#### Scenario: Generating a document download link for the frontend
- **WHEN** a presigned URL is generated for a browser to download a file
- **THEN** the URL is built against the public MinIO endpoint, not the internal one

### Requirement: Inline-viewable content disposition
Presigned URLs intended for in-browser viewing MUST set `Content-Disposition: inline`, not `attachment`.

#### Scenario: A user opens a document in the in-app viewer
- **WHEN** a presigned URL is generated for viewing a document inline
- **THEN** the response's `Content-Disposition` header is `inline`

### Requirement: Knowledge-base bucket is the only wired storage domain
Only `KnowledgeBaseStorageService` MUST be instantiated and injected via the DI container; `UsersStorageService` and `ProjectsStorageService` remain unwired until a router actually needs them.

#### Scenario: A future feature needs per-user file storage
- **WHEN** a new capability requires storing files in the `users` bucket
- **THEN** it must explicitly wire `UsersStorageService` into the container — it is not available by default today
