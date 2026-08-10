## Purpose
Celery/Flower task monitoring and live infrastructure health dashboard for the admin panel.

## Requirements

### Requirement: Concurrent multi-service health probing
The health check MUST probe all dependent services (rag_service, Qdrant, MinIO, Postgres, Redis) concurrently with a bounded timeout, not sequentially.

#### Scenario: One dependency is slow
- **WHEN** Qdrant takes 4 seconds to respond while other services respond in under 100ms
- **THEN** the overall health check does not block on Qdrant beyond its own timeout, and other services report their real status independently

### Requirement: Three-tier health classification
Each probed service MUST be classified as `online`, `degraded` (slow but responding), or `offline` (unreachable/erroring).

#### Scenario: Service responds slowly but successfully
- **WHEN** a probed service responds successfully but takes longer than 500ms
- **THEN** it is classified as `degraded`, not `online`

### Requirement: Task revocation always terminates
Revoking a Celery task via the admin panel MUST always request forceful termination (`terminate=true`) from Flower.

#### Scenario: Admin revokes an in-flight task
- **WHEN** an admin revokes a task that is currently executing
- **THEN** the revoke request to Flower is sent with `terminate=true`
