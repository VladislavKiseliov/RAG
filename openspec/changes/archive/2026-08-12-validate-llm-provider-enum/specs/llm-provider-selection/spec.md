## MODIFIED Requirements

### Requirement: Provider selection via LLM_PROVIDER
The system SHALL select which LLM backend to use at startup based on the `LLM_PROVIDER` configuration value, supporting exactly the values `openai_compat`, `groq`, and `openrouter` (default: `openrouter`). Any value not in this set SHALL cause a validation error at settings instantiation time, before the service begins handling requests.

Note: this corrects a pre-existing documentation error — the default was previously (incorrectly) documented here as `openai_compat`, while `llm_service/settings.py` has always defaulted to `openrouter`. The code is unchanged; only the spec text is corrected to match it.

#### Scenario: Default provider when unset
- **WHEN** `LLM_PROVIDER` is not set in configuration
- **THEN** the system SHALL construct a provider that sends requests to `https://openrouter.ai/api/v1` authenticated with `OPENROUTER_API_KEY`

#### Scenario: OpenRouter provider selected
- **WHEN** `LLM_PROVIDER` is set to `openrouter`
- **THEN** the system SHALL construct a provider that sends requests to `https://openrouter.ai/api/v1` authenticated with `OPENROUTER_API_KEY`

#### Scenario: Invalid provider value rejected
- **WHEN** `LLM_PROVIDER` is set to an unsupported value (e.g., `openroute`, `custom`, or any value not in the set `{openai_compat, groq, openrouter}`)
- **THEN** the system SHALL raise a validation error at startup and not proceed to service initialization
