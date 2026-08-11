## Context

See `proposal.md` for motivation. Facts shaping the approach:

- `llm_service/LLM_provider.py` currently has `OpenAICompatLLMProvider` (generic, `base_url`/`api_key` from settings) and `GroqLLMProvider` (hardcoded `base_url="https://router.huggingface.co/v1"`, dedicated `HF_TOKEN` credential) — the two are ~95% identical, differing only in `__init__`. Neither has direct unit tests today; `llm_service/tests/test_llm_gateway.py` mocks the `LLMProvider` Protocol instead of touching either concrete class.
- Provider selection is a single `if/else` in `infrastructure.py::_build_llm_provider()`, keyed on `settings.LLM_PROVIDER` (plain `str`, default `"openai_compat"`, no enum/Literal validation today).
- OpenRouter's chat completions endpoint is `https://openrouter.ai/api/v1/chat/completions`, OpenAI-compatible, reachable via the already-vendored `openai` SDK's `AsyncOpenAI(api_key=..., base_url="https://openrouter.ai/api/v1")` — no new HTTP client needed.
- `ai_config.toml`'s `[llm]`/`[llm_summary]` sections already carry `model_name` independent of which provider is active — no provider-specific model config exists or is needed.

## Goals / Non-Goals

**Goals:**
- `OpenRouterLLMProvider` selectable via `LLM_PROVIDER=openrouter`, implementing the full `LLMProvider` Protocol (all 9 methods), authenticated via a dedicated `OPENROUTER_API_KEY`.
- Fail fast: constructing the provider with an empty key raises immediately (matches `OpenAICompatLLMProvider`/`GroqLLMProvider`'s existing `if not api_key: raise ValueError(...)` pattern), not on first request.

**Non-Goals:**
- OpenRouter's `reasoning`/`reasoning_details` parameters — confirmed out of scope with the user. No changes to `LLMProvider` Protocol signatures, `LLMGateway`, or chat message/history schemas.
- Consolidating `OpenAICompatLLMProvider`/`GroqLLMProvider`/`OpenRouterLLMProvider` into one generic parameterized class — flagged in `proposal.md` as a reasonable future follow-up, not part of this change (surgical: don't touch the two working providers).
- Optional OpenRouter ranking headers (`HTTP-Referer`, `X-Title`) — explicitly optional per OpenRouter's own docs, skipped for the same reason as reasoning: minimal footprint for basic connectivity.
- Validating `LLM_PROVIDER` against an enum/Literal — out of scope; it's a plain `str` today for the two existing values too, not something this change needs to fix to add a third value.

## Decisions

**New class over extending `OpenAICompatLLMProvider` with a provider-name switch inside it.** Alternative considered: make `OpenAICompatLLMProvider` itself branch on a `provider` argument to pick between `LLM_BASE_URL` and a hardcoded OpenRouter URL. Rejected: `GroqLLMProvider` already established the precedent of "one class per provider, hardcoded base_url, dedicated credential field" — matching that shape keeps `OpenRouterLLMProvider` a pure addition with zero lines changed in the two existing classes, at the cost of continuing the duplication (explicitly acknowledged, not fixed, in `proposal.md`).

**Dedicated `OPENROUTER_API_KEY`, not reusing `LLM_API_KEY`.** Mirrors `HF_TOKEN` being separate from `LLM_API_KEY` for Groq — lets an operator keep credentials for all three providers configured simultaneously and switch via `LLM_PROVIDER` alone, without overwriting `LLM_API_KEY` each time. Matches the "alternative selectable provider" scope confirmed with the user (not a replacement).

**Default value for `OPENROUTER_API_KEY`.** `str = ""` (empty default, same as `HF_TOKEN`), not a required field — so `LLMSettings` still constructs successfully for operators who never select `openrouter`. The fail-fast check lives in `OpenRouterLLMProvider.__init__`, not in settings validation, matching how `GroqLLMProvider` already handles `HF_TOKEN`.

## Risks / Trade-offs

- [Third near-duplicate ~140-line class] → Accepted, explicitly deferred (see Non-Goals) — matches existing precedent, and consolidating now would touch two working, presumably-in-use provider classes for a change that only needs to add a third.
- [No test today exercises `GroqLLMProvider`'s actual HTTP call shape, and this change doesn't add that for `OpenRouterLLMProvider` either] → Accepted: matches existing test coverage precedent for this file (constructor validation is the only thing tested at this layer; `test_llm_gateway.py` covers the actual generation-call contract via the `LLMProvider` Protocol mock, provider-agnostic).

## Migration Plan

Not applicable (additive, no existing behavior changes, no data migration). Order of work:
1. `OPENROUTER_API_KEY` field in `LLMSettings`.
2. `OpenRouterLLMProvider` class in `LLM_provider.py`.
3. Third branch in `_build_llm_provider()`.
4. `.env.example` documentation.
5. Constructor-validation test + provider-selection test.
6. Manual smoke: set `LLM_PROVIDER=openrouter` + a real `OPENROUTER_API_KEY` + `ai_config.toml`'s `model_name = "deepseek/deepseek-v4-flash-0731"` locally, confirm a real chat answer round-trips.
