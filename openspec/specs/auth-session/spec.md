## Purpose
Login/register flow and JWT access+refresh session management with proactive auto-refresh.

## Requirements

### Requirement: Proactive token refresh
The access token MUST be refreshed proactively when its expiry is within 60 seconds, rather than waiting for a request to fail with 401.

#### Scenario: A request is about to be made with a soon-expiring token
- **WHEN** the stored access token's `exp` is within 60 seconds of now
- **THEN** the token is refreshed before the outgoing request is sent

### Requirement: De-duplicated concurrent refresh
Multiple concurrent requests hitting an expiring token MUST share a single in-flight refresh call, not each trigger their own.

#### Scenario: Two API calls fire near-simultaneously with an expiring token
- **WHEN** two requests both detect the access token is expiring at nearly the same time
- **THEN** only one refresh call is made, and both requests wait on its result

### Requirement: Forced logout on refresh failure
If the refresh call itself fails, the client MUST force a logout rather than retry indefinitely or proceed with a stale token.

#### Scenario: The refresh token has been revoked or expired
- **WHEN** a refresh attempt fails
- **THEN** the client clears the session and returns the user to the login screen
