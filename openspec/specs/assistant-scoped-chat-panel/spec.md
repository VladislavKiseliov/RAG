## Purpose
Ephemeral, contextual AI chat dockable inside Knowledge Base and Projects screens. The context-prefix mechanism is a text prefix on the user's message, not true scoped retrieval.

## Requirements

### Requirement: Fresh instance per mount, no persisted history
Each time the panel is opened, it MUST start with a fresh chat instance; history from a previous open of the panel MUST NOT persist.

#### Scenario: A user closes and reopens the assistant panel
- **WHEN** the panel is closed and reopened, even for the same document
- **THEN** the conversation starts empty, with no memory of the earlier session

### Requirement: Context prefix is textual, not retrieval-scoped
Messages sent from this panel MUST be prefixed with document/project context text (e.g. `Вопрос по документу "{title}": …`); this MUST NOT be presented to the user as if retrieval were actually scoped to that specific document.

#### Scenario: A user asks a question from within a document's assistant panel
- **WHEN** the message is sent
- **THEN** it includes a text prefix naming the document, but the underlying search still queries the full knowledge base, not just that document

### Requirement: Save-to-notes and export actions
After the first assistant response, the panel MUST offer both saving the exchange to Notes (via the real notes API) and exporting it as a local text file.

#### Scenario: A user gets a first response in the panel
- **WHEN** the first assistant reply arrives
- **THEN** "Save to Notes" and "Export .txt" actions become available
