## 1. Update Settings with Literal Validation

- [x] 1.1 Update `llm_service/settings.py` to change `LLM_PROVIDER: str = "openrouter"` to `LLM_PROVIDER: Literal["openai_compat", "groq", "openrouter"] = "openrouter"` — default value unchanged
- [x] 1.2 Add `from typing import Literal` import at the top of settings.py if not already present

## 2. Add Validation Test

- [x] 2.1 New `llm_service/tests/test_settings.py` — constructs `LLMSettings` directly (`_env_file=None` + explicit required kwargs) with an invalid `LLM_PROVIDER` value, asserts `pydantic.ValidationError`
- [x] 2.2 Test asserts the error message mentions the three valid values (`match="openai_compat"`, and manually confirmed the full message names all three)
- [x] 2.3 Parametrized test verifies each of the three valid values is accepted without error, plus a dedicated test confirming the unset/default case is still `"openrouter"`

## 3. Update Existing Provider Resolution Tests

- [x] 3.1 `test_infrastructure_provider_selection.py`/`test_infrastructure_provider_credentials.py` needed no changes — default unchanged, all pass as-is
- [x] 3.2 No test hardcodes an invalid `LLM_PROVIDER` string — nothing to fix

## 4. Run Full Test Suite

- [x] 4.1 `llm_service/.venv/Scripts/python.exe -m pytest llm_service/tests -q` — 237 passed (232 pre-existing + 5 new)
- [x] 4.2 Grepped the repo for other `LLMSettings(` construction sites — none found outside `settings.py` itself

## 5. Verification

- [x] 5.1 Confirmed invalid value raises `ValidationError` at construction (manual repro, see below)
- [x] 5.2 Confirmed the real `.env` (`LLM_PROVIDER=openrouter`) still imports cleanly via the actual `llm_service.settings.settings` singleton — no live breakage
- [x] 5.3 Error message: `Input should be 'openai_compat', 'groq' or 'openrouter' [type=literal_error, input_value='typo', input_type=str]` — clear, lists all three
