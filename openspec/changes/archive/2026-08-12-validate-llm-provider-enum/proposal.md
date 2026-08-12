## Why

The `LLM_PROVIDER` setting in `llm_service/settings.py` is currently a plain `str` without validation, accepting any value. This creates risk: typos in configuration (e.g., `LLM_PROVIDER=openroute` instead of `openrouter`) are not caught until the service starts building infrastructure, leading to silent fallback to default credentials and unclear error messages. Validation against the three actually-supported values (`openai_compat`, `groq`, `openrouter`) was explicitly deferred during the recent LLM provider consolidation and is ready to be implemented now.

## What Changes

- `llm_service/settings.py:18` — `LLM_PROVIDER` field type changes from `str` to `Literal["openai_compat", "groq", "openrouter"]`, enforced by pydantic at settings instantiation. **Default value stays `"openrouter"`** — changing it is explicitly out of scope (would be a separate, deliberate breaking change).
- Corresponding test updates to ensure invalid values are rejected at settings load time.
- No changes to `infrastructure.py` logic or any caller code — the three values map to the same `base_url`/`api_key` resolution as before.
- The existing base spec `llm-provider-selection` already (incorrectly) documented the default as `openai_compat` — a pre-existing drift from the code's actual `"openrouter"` default, predating this change. Since this change touches the same requirement anyway, the delta corrects the spec text to match the actual (unchanged) code default instead of leaving the documented mismatch in place.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `llm-provider-selection`: Adding validation to enforce that only the three documented provider names (`openai_compat`, `groq`, `openrouter`) are accepted — invalid values are now rejected at startup with a clear validation error, rather than silently falling back to default credentials.

## Impact

- **Affected code:** `llm_service/settings.py`, test suite for settings loading
- **Affected systems:** llm_service only (settings instantiation at startup)
- **Breaking change:** Any deployment passing an undocumented `LLM_PROVIDER` value will now fail fast with a validation error, requiring explicit use of one of the three documented values. This is intentional and improves observability.
- **No impact to:** inference logic, provider-selection algorithm, backwards compatibility within the three supported values
