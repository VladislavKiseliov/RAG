## Purpose
JWT-based login/registration/refresh/logout for the internal assistant, with anti-enumeration and rate-limiting guarantees.

## Requirements

### Requirement: Generic auth errors
Login and registration MUST NOT reveal whether a failure was caused by a missing user or a wrong password.

#### Scenario: Login with unknown login vs wrong password
- **WHEN** a client calls `POST /auth/login` with a login that doesn't exist, or with a valid login but wrong password
- **THEN** both cases return the same `InvalidCredentialsError` response, indistinguishable to the caller

### Requirement: Refresh-token rotation
Refreshing an access token MUST atomically revoke the old refresh token and issue a new one.

#### Scenario: Token refresh
- **WHEN** a client calls `POST /auth/refresh` with a valid refresh token
- **THEN** the old refresh token is revoked and a new access+refresh token pair is returned; the old refresh token can no longer be used

### Requirement: Logout revocation
Logout MUST be idempotent and support revoking all sessions for a user, not just the current one.

#### Scenario: Logout with revoke_all
- **WHEN** a client calls `POST /auth/logout` with `revoke_all=true`
- **THEN** all refresh tokens for that user are revoked, and calling logout again does not error

### Requirement: Per-IP rate limiting on auth endpoints
Login and registration MUST be rate-limited per source IP (via `X-Real-IP`) to slow down credential-stuffing and mass-registration.

#### Scenario: Exceeding login rate limit
- **WHEN** more than 10 login attempts occur from the same IP within one minute
- **THEN** further attempts are rejected until the window resets, independent of which login is being tried
