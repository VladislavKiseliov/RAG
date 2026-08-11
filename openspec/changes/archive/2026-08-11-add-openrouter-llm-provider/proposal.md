## Why

`llm_service` currently supports exactly two hardcoded LLM backends (`openai_compat`/gatellm and `groq`, selected via `LLM_PROVIDER`), each a near-duplicate `LLMProvider` class differing only in client construction. We want `deepseek/deepseek-v4-flash-0731` available through OpenRouter as a third selectable option, without disturbing the two existing ones — OpenRouter is itself an OpenAI-compatible API, so this follows the same pattern `GroqLLMProvider` already established rather than inventing a new one.

## What Changes

- Add `OpenRouterLLMProvider` to `llm_service/LLM_provider.py`, mirroring `GroqLLMProvider`'s shape: hardcoded `base_url="https://openrouter.ai/api/v1"`, a dedicated `OPENROUTER_API_KEY` credential (kept separate from `LLM_API_KEY`/`HF_TOKEN`, same as Groq's `HF_TOKEN`).
- Add `OPENROUTER_API_KEY: str = ""` to `LLMSettings` (`llm_service/settings.py`).
- Add a third branch to `_build_llm_provider()` (`llm_service/infrastructure.py`): `LLM_PROVIDER == "openrouter"` → `OpenRouterLLMProvider`.
- Document `OPENROUTER_API_KEY` and the new `LLM_PROVIDER=openrouter` value in the root `.env.example`'s existing LLM block.
- Model selection stays exactly as it already works today: whichever provider is active reads `model_name` from `ai_config.toml`'s `[llm]`/`[llm_summary]` sections (no new config section needed) — set to `deepseek/deepseek-v4-flash-0731` when OpenRouter is the active provider.
- Explicitly out of scope (confirmed with the user): OpenRouter's `reasoning`/`reasoning_details` parameters (step-by-step reasoning continuity across turns). This provider makes plain, non-reasoning requests only — same shape as the other two providers. No changes to `LLMProvider` Protocol, `LLMGateway`, or chat history/message schemas.

## Capabilities

### New Capabilities
- `llm-provider-selection`: how `llm_service` selects and authenticates against one of several OpenAI-compatible LLM backends via `LLM_PROVIDER` config, and what each selectable value requires.

### Modified Capabilities
(none)

## Impact

- Affected code: `llm_service/LLM_provider.py` (new class), `llm_service/settings.py` (new field), `llm_service/infrastructure.py` (new branch), `.env.example` (new documented vars).
- No changes to `LLMProvider` Protocol, `LLMGateway`, prompt construction, or any call site — `OpenRouterLLMProvider` implements the same 9 methods as its siblings, purely additive.
- No changes to the two existing providers (`OpenAICompatLLMProvider`, `GroqLLMProvider`) — this is additive, not a refactor. Note (not fixed here): this makes `LLM_provider.py` a third near-duplicate of the same ~140-line class shape; consolidating it into one generic class parameterized by `base_url`/`api_key` would be a reasonable separate follow-up, not part of this change.
- Runtime dependency: none new — OpenRouter is reached via the already-vendored `openai` SDK, same as the other two providers.
