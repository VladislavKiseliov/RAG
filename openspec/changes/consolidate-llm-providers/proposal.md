## Why

`llm_service/LLM_provider.py` now has three ~140-line classes (`OpenAICompatLLMProvider`, `GroqLLMProvider`, `OpenRouterLLMProvider`) that are byte-for-byte identical except for `__init__` (3 lines: `base_url` source and which settings field supplies the API key). Adding OpenRouter (archived `2026-08-11-add-openrouter-llm-provider`) deliberately kept this duplication rather than touch the two working providers mid-change — but now that there are three copies instead of two, and a fourth provider is plausible later, consolidating is cheap while the classes are simple and fresh, and gets more expensive with every future provider added the same way.

## What Changes

- Delete `GroqLLMProvider` and `OpenRouterLLMProvider` entirely. `OpenAICompatLLMProvider` becomes the only provider class — it already takes `base_url`/`api_key` as constructor arguments, so no change to the class itself.
- Move the "which base_url / which settings field" decision into `_build_llm_provider()` (`llm_service/infrastructure.py`) as a small per-provider lookup table, replacing the current `if/elif/else` chain that calls three different classes.
- Fail-fast behavior (raise before startup completes if the selected provider's credential is empty) is preserved, but the check and its error message move from each provider class's `__init__` to `_build_llm_provider()`.
- No change to `LLMProvider` Protocol, `LLMGateway`, `LLMSettings` fields, `ai_config.toml`, or any call site — every existing `LLM_PROVIDER` value (`openai_compat`, `groq`, `openrouter`) continues to resolve to the exact same `base_url`/credential pairing as before.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — pure internal refactor, `LLM_PROVIDER`'s observable behavior is unchanged for all three existing values. `skip_specs: true` set in `.openspec.yaml`.)

## Impact

- Affected code: `llm_service/LLM_provider.py` (delete 2 classes, ~280 lines), `llm_service/infrastructure.py` (`_build_llm_provider()` rewritten as a lookup table).
- Test impact: `llm_service/tests/test_infrastructure_provider_selection.py` (added in the OpenRouter change) already asserts `isinstance(provider, OpenRouterLLMProvider)`/`isinstance(provider, GroqLLMProvider)` — these assertions must change to check `isinstance(provider, OpenAICompatLLMProvider)` plus the resolved `base_url`/`api_key` instead, since the concrete class is now always the same. `llm_service/tests/test_llm_provider_openrouter.py` (constructor-validation test) has no equivalent target anymore — its assertions move to whatever now performs the fail-fast check.
- No production behavior change: all three `LLM_PROVIDER` values keep working identically from the outside.
