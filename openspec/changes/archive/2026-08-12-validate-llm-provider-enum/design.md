## Context

See proposal.md - Why section for motivation.

Current state facts:
- `llm_service/settings.py:18` defines `LLM_PROVIDER: str = "openrouter"` — a bare string field with no validation.
- `llm_service/infrastructure.py:28-33` contains the selection logic in `_resolve_provider_config()`, which branches on `settings.LLM_PROVIDER` value to determine base_url and credential field: `"groq"` → HF router + HF_TOKEN, `"openrouter"` → OpenRouter API + OPENROUTER_API_KEY, anything else → defaults to `LLM_BASE_URL` + `LLM_API_KEY`.
- Per the existing spec `openspec/specs/llm-provider-selection/spec.md`, the three valid values are `openai_compat` (default/custom), `groq`, and `openrouter`.
- `LLMSettings` uses `pydantic_settings.BaseSettings` with `SettingsConfigDict`, inheriting pydantic v2 validation.
- No current tests explicitly validate rejection of invalid `LLM_PROVIDER` values — tests assert on resolved `base_url` but not on pre-resolution setting values.

## Goals / Non-Goals

**Goals:**
- Reject invalid `LLM_PROVIDER` values at settings instantiation (when pydantic loads env vars / TOML / defaults), preventing the service from starting with a misconfiguration.
- Provide a clear validation error message naming the three supported values.
- Keep error message construction and default-case naming consistent with infrastructure.py logic.

**Non-Goals:**
- Changing the resolution algorithm in infrastructure.py or the three provider behaviors.
- Adding a new provider or removing support for any existing value.
- Retroactive validation on already-instantiated settings objects (validation happens once at startup).
- Changing the default value (stays `"openrouter"`) — a separate, deliberate breaking change, not part of this request.

## Decisions

**Decision: Use pydantic `Literal[...]` type annotation in `LLMSettings.LLM_PROVIDER`.**

Rationale:
- pydantic v2 (used by pydantic-settings) validates Literal types natively at field instantiation, enforcing the set at the type level.
- Syntax is clean and declarative: `LLM_PROVIDER: Literal["openai_compat", "groq", "openrouter"] = "openrouter"`.
- Pydantic's error messages for Literal violations are clear and auto-generated.
- No custom validator code is needed; the validation logic is implicit in the type.

Alternatives considered:
- Custom validator using `@field_validator` — more verbose, duplicates logic already in infrastructure.py, harder to maintain if valid values change.
- `Enum` class — adds unnecessary abstraction; Literal is idiomatic in Python 3.10+ and requires no class definition.
- Manual string checks in infrastructure.py before construction — too late to fail fast; errors would be less clear.

**Decision: Keep the default value `"openrouter"` — do not change it.**

Rationale:
- User explicitly declined the default-value change when this was raised: validation only, current runtime behavior (including for deployments relying on the implicit default) must not change.
- The base spec's claim that the default is `"openai_compat"` predates this change and was never true of the code — `settings.py:18` has always defaulted to `"openrouter"`. That mismatch is corrected here at the documentation level (spec text updated to say `"openrouter"`), not by changing code to match the wrong spec.
- Adding `Literal[...]` with the existing default is a pure validation tightening — every currently-working deployment (explicit or relying on the implicit default) keeps working identically; only genuinely invalid/typo'd values start failing fast.

**Decision: Add a test that verifies invalid `LLM_PROVIDER` values are rejected.**

Rationale:
- Currently, tests in `llm_service/tests/test_infrastructure_provider_selection.py` validate that each of the three values produces the correct base_url, but not that invalid values are caught.
- A regression test ensures the validation is not accidentally lost in future refactors.
- Test structure: instantiate `LLMSettings` with an invalid `LLM_PROVIDER` value (e.g., in a test env var), catch `pydantic.ValidationError`, assert the error message mentions the allowed values.

## Risks / Trade-offs

- [A deployment currently passing an undocumented/typo'd `LLM_PROVIDER` value — if any exist — will now fail fast at startup instead of silently falling through to the `openai_compat` branch.] → Accepted: this is the intended behavior change (the whole point of the validation). Deployments using one of the three real values (including relying on the unset/default case, which stays `"openrouter"`) are unaffected.
- [pydantic's Literal error message may not be customized.] → Accepted: The auto-generated message is clear enough (e.g., "Input should be 'openai_compat', 'groq', or 'openrouter'"). If a more specific message is needed later, a custom validator can wrap it.

## Migration Plan

Deployment steps (one-time, one-way):
1. Update `LLMSettings.LLM_PROVIDER` field type in settings.py (default unchanged: `"openrouter"`).
2. Add validation test.
3. Deploy to dev/staging first; verify no existing deployments break.
4. Before production deploy: audit all production `.env` files and config for any undocumented `LLM_PROVIDER` value — none expected, since the three real values are the only ones `infrastructure.py` has ever branched on.
5. Deploy to production; roll out monitoring/alerts for `LLMSettings` validation errors (should be zero if audit is complete).
6. After deploy: one-week observation window; no rollback needed if startup validation fails (it's correct behavior; misconfiguration is the root cause, not the code).

No data migration or backwards-compatibility layer is needed — this is a startup-time settings change only.
