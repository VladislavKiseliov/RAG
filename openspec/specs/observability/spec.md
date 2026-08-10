## Purpose
Cross-cutting request logging, Prometheus metrics, and a consistent error-response envelope for the backend service.

## Requirements

### Requirement: Metrics endpoint excluded from its own metrics
Requests to `/metrics` MUST be excluded from access logs and from the request-duration histogram, to avoid the scraper polluting its own data.

#### Scenario: Prometheus scrapes /metrics
- **WHEN** a scraper calls `GET /metrics` repeatedly
- **THEN** these calls do not appear in access logs or affect latency histograms

### Requirement: Consistent error envelope
Every custom `AppError` subclass MUST map to a consistent `{status, code, message}` JSON response shape.

#### Scenario: A domain error is raised
- **WHEN** any endpoint raises a subclass of `AppError`
- **THEN** the client receives a JSON body with `status`, `code`, and `message` fields, regardless of which error type it was

### Requirement: No internal leakage on uncaught exceptions
Uncaught exceptions MUST be logged server-side with a stack trace but returned to the client as a generic 500 without internal details.

#### Scenario: An unexpected exception occurs
- **WHEN** a request triggers an exception not handled by any specific error type
- **THEN** the client receives a generic 500 response with no stack trace or internal message, while the server log contains the full trace
