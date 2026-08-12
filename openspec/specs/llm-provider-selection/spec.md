## Purpose

Defines how `llm_service` selects and authenticates against one of several OpenAI-compatible LLM backends at startup, and what each selectable value requires to construct successfully.

## Requirements

### Requirement: Provider selection via LLM_PROVIDER
The system SHALL select which LLM backend to use at startup based on the `LLM_PROVIDER` configuration value, supporting exactly the values `openai_compat`, `groq`, and `openrouter` (default: `openrouter`). Any value not in this set SHALL cause a validation error at settings instantiation time, before the service begins handling requests.

#### Scenario: Default provider when unset
- **WHEN** `LLM_PROVIDER` is not set in configuration
- **THEN** the system SHALL construct a provider that sends requests to `https://openrouter.ai/api/v1` authenticated with `OPENROUTER_API_KEY`

#### Scenario: OpenRouter provider selected
- **WHEN** `LLM_PROVIDER` is set to `openrouter`
- **THEN** the system SHALL construct a provider that sends requests to `https://openrouter.ai/api/v1` authenticated with `OPENROUTER_API_KEY`

#### Scenario: Invalid provider value rejected
- **WHEN** `LLM_PROVIDER` is set to an unsupported value (e.g., `openroute`, `custom`, or any value not in the set `{openai_compat, groq, openrouter}`)
- **THEN** the system SHALL raise a validation error at startup and not proceed to service initialization

### Requirement: Provider construction fails fast on missing credentials
The system SHALL raise an error at provider construction time (not on first request) when the credential required by the selected `LLM_PROVIDER` value is empty or unset.

#### Scenario: OpenRouter selected without a key
- **WHEN** `LLM_PROVIDER` is `openrouter` and `OPENROUTER_API_KEY` is empty
- **THEN** the system SHALL raise an error before the service starts handling requests, not on the first LLM call

### Requirement: Provider-agnostic call surface
Every selectable provider SHALL implement the same generation methods (answer generation, streaming, general-purpose completion, JSON-contract completion, summaries, note generation, chapter/document/table summaries) so that switching `LLM_PROVIDER` requires no changes to any caller.

#### Scenario: Switching provider changes no call sites
- **WHEN** an operator changes `LLM_PROVIDER` from `groq` to `openrouter` and restarts the service
- **THEN** every existing feature (chat answers, streaming, summaries, notes) SHALL continue to function without code changes elsewhere in `llm_service`
