## 1. Settings

- [x] 1.1 Add `OPENROUTER_API_KEY: str = ""` to `LLMSettings` in `llm_service/settings.py`

## 2. Provider class

- [x] 2.1 Add `OpenRouterLLMProvider` to `llm_service/LLM_provider.py`, mirroring `GroqLLMProvider`'s shape: `__init__(self, *, api_key: str)` raising `ValueError` if `api_key` is falsy, `AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", timeout=60.0)`, and all 9 `LLMProvider` Protocol methods (`generate`, `generate_stream`, `generate_general`, `generate_json_raw`, `generate_summary`, `generate_note`, `generate_chapter_summary`, `generate_document_summary`, `generate_table_summary`, `aclose`) with bodies identical to `GroqLLMProvider`'s

## 3. Wiring

- [x] 3.1 Add `elif settings.LLM_PROVIDER == "openrouter": return OpenRouterLLMProvider(api_key=settings.OPENROUTER_API_KEY)` branch to `_build_llm_provider()` in `llm_service/infrastructure.py`, and import `OpenRouterLLMProvider`

## 4. Documentation

- [x] 4.1 Add `OPENROUTER_API_KEY=your_openrouter_api_key_here` to the `.env.example` LLM block (near `LLM_PROVIDER`/`LLM_API_KEY`), with a comment noting `LLM_PROVIDER=openrouter` as the third selectable value and a link to https://openrouter.ai/keys

## 5. Tests

- [x] 5.1 `llm_service/tests/test_llm_provider_openrouter.py` — constructing `OpenRouterLLMProvider` with an empty `api_key` raises `ValueError`; constructing with a non-empty key succeeds
- [x] 5.2 Extend or add a test for `_build_llm_provider()`'s selection logic — `LLM_PROVIDER=openrouter` returns an `OpenRouterLLMProvider` instance (mock/monkeypatch `settings`, don't require a real key) — also covers `groq`/`openai_compat` branches for regression safety

## 6. Verification

- [x] 6.1 Run `llm_service`'s test suite, confirm no regressions — **230/230 passed**
- [x] 6.2 Manual smoke test: set `LLM_PROVIDER=openrouter`, a real `OPENROUTER_API_KEY`, and `ai_config.toml`'s `[llm].model_name = "deepseek/deepseek-v4-flash-0731"` locally; confirm a real chat request round-trips a non-empty answer — **confirmed**, `OpenRouterLLMProvider.generate_general()` round-tripped a real non-empty Cyrillic answer through the live OpenRouter API
