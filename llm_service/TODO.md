# LLM Service — TODO

## Критические ✅ Всё исправлено

### 1. ~~RetrieveItem схема~~ ✅
Схемы `rag_service` и `llm_service` совпадают: `child_chunks`, `parent_chunk`, `metadata`.

### 2. ~~route не доходит до generate()~~ ✅
`FinalPromptData` содержит `route: str`, `build_prompt_node` передаёт `route=state.route`.

### 3. ~~sources всегда []~~ ✅
`agent_routers.py` маппит `retrieval_data → sources` корректно.

### 4. ~~Дебажные print()~~ ✅
Убраны из `lean_rag_agent.py` и `retrieve_service.py`.

### 5. ~~context type mismatch~~ ✅
`context=None` возвращается напрямую, `include_context` не используется.

---

## Остаётся

- [x] Structured logging — `utils/logger_config.py` (`CustomJsonFormatter`), все ноды графа логируют через `extra={...}` (проверено 2026-07-17, было отмечено как незавершённое — стало стейл)
- [~] Тесты — ноды `expand`/`retrieve`/`generate` покрыты (`tests/test_lean_rag_agent.py`, 27 тестов), но end-to-end `LeanRagAgent.run()`/`self.app.ainvoke` ничем не покрыт
- [x] Убрать мёртвый код: `promt/promts.py` (промпты перенесены в `ai_config.toml`, файл удалён)
- [x] Убрать мёртвый код: `agent_service.py`, `answer_service.py` — файлов больше нет в репозитории (проверено 2026-07-17, было отмечено как незавершённое — стало стейл)
- [ ] `max_tokens` есть в `ai_config.toml` (`[llm]`) и валидируется в `AppConfig`, но нигде не передаётся в `chat.completions.create()` — решение отложено намеренно, вернуться к этому позже

---

## ML-роутер (e5 + LogReg) — статус на 2026-07-17

- [x] Обучение/классификатор существуют (`ml_router/train.py`, `intent_model_small.pkl`)
- [x] Роутер реально вызывается в проде: `infrastructure.py` строит `MLQueryRouter` → `LeanRagAgent.route_node` (`application/lean_rag_agent.py`) вызывает `.route()` на каждый запрос — не только автономный скрипт
- [x] ~~Несоответствие модели эмбеддера~~ — ложная тревога (проверено 2026-07-20). `ml_router/train.py` действительно обучает на e5-small (`intent_model_small.pkl`), но `.env`/`.env.example` (`ML_ROUTER_MODEL_PATH`) указывают на `intent_model.pkl` — отдельный артефакт, обученный на e5-large (см. `ml_router/test_model.py:MODEL_NAME`), совпадает с эмбеддером в `infrastructure.py`. `train.py`/`intent_model_small.pkl` — просто старый неиспользуемый скрипт/артефакт, не риск в проде
- [x] `route_node` блокировал event loop ✅ 2026-07-20 — `.route()` вызывается через `asyncio.to_thread` в `lean_rag_agent.py`
- [x] Второй неиспользуемый `MLQueryRouter` в `application/services/query_service.py` ✅ 2026-07-22 — удалён (был мёртвым кодом с другим порогом, 0.5 вместо 0.6 в проде, вводил в заблуждение). Заодно поправлена опечатка `row_query` → `raw_query` в `QueryExpansionService.expand()` (был найден внешним код-ревью 2026-07-21, см. `rag_service/ISSUES.md`-стиль пунчлиста)