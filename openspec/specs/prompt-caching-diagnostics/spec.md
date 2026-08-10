## Purpose
Manual diagnostic tooling (not a production code path) for verifying whether the LLM gateway actually honors prompt caching. Empirically found (2026-08-07) that gatellm.ru's `cached_tokens` field does not vary meaningfully with prefix match — prompt caching provides no real savings on this gateway. No production behavior currently depends on caching.

## Requirements

### Requirement: Cache-hit comparison via matched vs mismatched prefix
The diagnostic script MUST compare `usage.prompt_tokens_details.cached_tokens` across repeated calls with an identical long system prefix against a control call with a reversed/different prefix.

#### Scenario: Running the diagnostic against the LLM gateway
- **WHEN** `prompt_cache_check_manual.py` is run
- **THEN** it reports `cached_tokens` for both the matched-prefix calls and the mismatched control call, so a human can judge whether caching is actually active

### Requirement: Diagnostic only, not gating production behavior
No production request path MUST assume caching provides latency or cost savings based on this script's findings, since the finding is gateway-specific and could change if the gateway changes.

#### Scenario: A future feature considers relying on prompt caching for cost savings
- **WHEN** prompt caching is proposed as a cost optimization
- **THEN** this diagnostic must be re-run against the current gateway before relying on it, rather than assuming the 2026-08-07 finding still holds
