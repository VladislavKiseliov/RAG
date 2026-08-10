## Purpose
AppRail icon-rail navigation, section routing, and the unified profile/settings menu.

## Requirements

### Requirement: Role-gated admin icon
The admin section icon in the rail MUST only appear if the current user's profile indicates admin role, fetched from the real profile endpoint.

#### Scenario: A non-admin user opens the app
- **WHEN** `currentUser.isAdmin` is false
- **THEN** the admin rail icon is not rendered

### Requirement: URL is the source of truth for the active section
Switching sections MUST navigate the URL, and the active section state MUST be derived from the URL, not from independent client state that could desync from the address bar.

#### Scenario: A user navigates directly to /knowledge via a bookmark
- **WHEN** the app loads with `/knowledge` in the URL
- **THEN** the Knowledge Base section is shown as active, without requiring a rail click first
