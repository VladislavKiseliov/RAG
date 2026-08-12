## 1. Provider resolution

- [x] 1.1 Add `_ProviderConfig` (frozen dataclass: `base_url`, `api_key`, `key_name`) and `_resolve_provider_config()` to `llm_service/infrastructure.py`, covering all three `LLM_PROVIDER` values (`groq`, `openrouter`, default/`openai_compat`) with the exact `base_url`/credential/error-message pairing each has today
- [x] 1.2 Rewrite `_build_llm_provider()` to call `_resolve_provider_config()`, raise `ValueError(f"{config.key_name} is not set")` if `api_key` is empty, and construct a single `OpenAICompatLLMProvider(api_key=..., base_url=...)`

## 2. Delete the duplicate classes

- [x] 2.1 Delete `GroqLLMProvider` and `OpenRouterLLMProvider` from `llm_service/LLM_provider.py`; update `__all__` to drop both names
- [x] 2.2 Remove the now-unused `GroqLLMProvider`/`OpenRouterLLMProvider` imports from `llm_service/infrastructure.py`

## 3. Update tests

- [x] 3.1 `llm_service/tests/test_infrastructure_provider_selection.py` — change all three tests' assertions from `isinstance(provider, <ConcreteClass>)` to `isinstance(provider, OpenAICompatLLMProvider)` + assert the resolved `base_url` matches what that `LLM_PROVIDER` value should resolve to
- [x] 3.2 `llm_service/tests/test_llm_provider_openrouter.py` — replaced by `llm_service/tests/test_infrastructure_provider_credentials.py` (empty-key → `ValueError` naming the right var, for all three providers; non-empty openrouter → resolves `base_url`), old file deleted

## 4. Verification

- [x] 4.1 Run `llm_service`'s full test suite, confirm no regressions — 232 passed
- [x] 4.2 Manually confirm all three `LLM_PROVIDER` values (`groq`, `openrouter`, default) still resolve to the same `base_url` as before this change — covered directly by `test_infrastructure_provider_selection.py`'s `base_url` assertions per provider
