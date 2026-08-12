## Context

See `proposal.md` for motivation. Facts shaping the approach:

- `OpenAICompatLLMProvider.__init__` already accepts `base_url`/`api_key` as plain arguments and already has its own `if not api_key: raise ValueError("LLM_API_KEY is not set")` guard — it needs zero changes to become the sole provider class.
- `GroqLLMProvider`/`OpenRouterLLMProvider` differ from `OpenAICompatLLMProvider` only in `__init__`: hardcoded `base_url`, and a different settings field (`HF_TOKEN`/`OPENROUTER_API_KEY`) feeding `api_key`, with a correspondingly different error message on empty key.
- `_build_llm_provider()` (`llm_service/infrastructure.py`) is the only place any provider class is constructed anywhere in the codebase (confirmed by exploration before this change was proposed) — no test or other call site constructs `GroqLLMProvider`/`OpenRouterLLMProvider` directly.
- `llm_service/tests/test_infrastructure_provider_selection.py` and `test_llm_provider_openrouter.py` (both added in the OpenRouter change) currently assert on the concrete class returned/constructed — these need updating, not just leaving to bit-rot.

## Goals / Non-Goals

**Goals:**
- One provider class (`OpenAICompatLLMProvider`), zero behavior change for any existing `LLM_PROVIDER` value.
- Preserve today's per-provider error message on a missing credential (`"HF_TOKEN is not set"` etc.) — an operator misconfiguring `LLM_PROVIDER=openrouter` without `OPENROUTER_API_KEY` should still get told which variable is missing, not a generic `LLM_API_KEY` message.

**Non-Goals:**
- Changing `LLMProvider` Protocol, `LLMGateway`, `LLMSettings` fields, or `ai_config.toml`.
- Validating `LLM_PROVIDER` against an enum/Literal — same as the OpenRouter change, still a plain `str`, still out of scope here.
- Adding a fourth provider or any reasoning/reasoning_details support — unrelated to this refactor.

## Decisions

**Provider-specific credential/base_url resolution moves to `infrastructure.py` as a small table, not into `OpenAICompatLLMProvider` itself.** `OpenAICompatLLMProvider` stays exactly as it is today (generic, provider-agnostic) — the "which provider maps to which URL/credential" knowledge belongs at the selection site, not baked into the one remaining provider class. Sketch:

```python
@dataclass(frozen=True)
class _ProviderConfig:
    base_url: str
    api_key: str
    key_name: str  # for the error message only

def _resolve_provider_config() -> _ProviderConfig:
    if settings.LLM_PROVIDER == "groq":
        return _ProviderConfig("https://router.huggingface.co/v1", settings.HF_TOKEN, "HF_TOKEN")
    if settings.LLM_PROVIDER == "openrouter":
        return _ProviderConfig("https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    return _ProviderConfig(settings.LLM_BASE_URL, settings.LLM_API_KEY, "LLM_API_KEY")

def _build_llm_provider() -> LLMProvider:
    config = _resolve_provider_config()
    if not config.api_key:
        raise ValueError(f"{config.key_name} is not set")
    return OpenAICompatLLMProvider(api_key=config.api_key, base_url=config.base_url)
```

**Keep `OpenAICompatLLMProvider`'s own `if not api_key: raise ValueError(...)` guard, don't remove it.** It becomes redundant with the new check in `_resolve_provider_config()`'s caller (which runs first and produces the correctly-named error), but removing it would mean `OpenAICompatLLMProvider` could silently construct an `AsyncOpenAI` client with an empty key if ever called from anywhere else in the future. Leaving it costs nothing (surgical: don't touch the one class we're keeping) and keeps it safe as a standalone unit.

**Test updates, not test deletion.** `test_infrastructure_provider_selection.py`'s three tests change their assertion from `isinstance(provider, GroqLLMProvider)`/`isinstance(provider, OpenRouterLLMProvider)` to `isinstance(provider, OpenAICompatLLMProvider)` plus asserting the resolved `base_url` (accessible via `provider._client.base_url`, same pattern already used in `test_llm_provider_openrouter.py`). `test_llm_provider_openrouter.py`'s constructor-validation tests (empty-key-raises, non-empty-key-succeeds) get superseded by equivalent tests against `_resolve_provider_config()`/`_build_llm_provider()` directly, since that's where the check now lives — same coverage, different target.

## Risks / Trade-offs

- [Losing per-class isolation — a bug in credential resolution now affects all three providers at once instead of being contained to one class] → Accepted: the resolution logic is ~10 lines total and the three-way branch is exactly what today's `if/elif/else` in `_build_llm_provider()` already does, just returning data instead of an object.
- [Test churn in two recently-written test files] → Accepted, scoped explicitly in tasks.md — these tests are only a few days old and small.

## Migration Plan

Not applicable (internal refactor, no deploy/rollback distinction, no data migration). Order of work:
1. Add `_ProviderConfig`/`_resolve_provider_config()` to `infrastructure.py`, rewrite `_build_llm_provider()` to use it.
2. Delete `GroqLLMProvider`/`OpenRouterLLMProvider` from `LLM_provider.py`, update `__all__`.
3. Update the two affected test files.
4. Run `llm_service`'s full test suite, confirm no regressions and that all three `LLM_PROVIDER` values still resolve to their pre-change `base_url`.
