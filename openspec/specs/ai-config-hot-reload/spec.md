## Purpose
TOML-driven prompt/model/threshold configuration (`ai_config.toml`) with live reload, so prompt/threshold tuning doesn't require a redeploy.

## Requirements

### Requirement: Reload only on file change
Config MUST only be re-read from disk when the file's modification time has changed since the last read, not on every call, to keep the cheap stat-check overhead low under per-request access patterns.

#### Scenario: Config is accessed many times within one request
- **WHEN** `get_live_config()` is called ~20 times while handling one request and the file hasn't changed
- **THEN** the TOML file is parsed only once, not 20 times

### Requirement: Last-known-good config on read/parse failure
If reading or parsing `ai_config.toml` fails after a config was already successfully loaded once, the system MUST continue serving the last-known-good config rather than crashing.

#### Scenario: The config file is saved mid-edit with invalid TOML syntax
- **WHEN** `ai_config.toml` temporarily contains invalid syntax while being edited
- **THEN** requests continue being served using the previously loaded valid config

### Requirement: Separate model tiers in schema
The config schema MUST separate `llm` (main) and `llm_summary` (cheap) model tiers as distinct configuration sections.

#### Scenario: A caller requests the cheap tier's model name
- **WHEN** code reads `config.llm_summary.model`
- **THEN** it gets a value independent of `config.llm.model`, even if both point to the same underlying model today
