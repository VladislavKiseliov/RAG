# llm_service — План внедрения и статус

Companion к `ARCHITECTURE.md` (там — целевое состояние и принципы, здесь — гранулярный статус
по каждому куску и что делать дальше). Обновляется по факту сессий, не заранее. Статусы:
✅ реально работает · 🔶 в графе как заглушка/частично · ⬜ не начато.

Не путать с ROADMAP.md — тот ведётся отдельно вне репозитория.

---

## 1. Снапшот по шагам ARCHITECTURE.md §10

| # | Шаг | Статус | Комментарий |
|---|---|---|---|
| 0 | Чистка git-истории, .idea/BOM/переименования, uv lock | 🔶 | git-история/BOM/переименования сделаны (`rag_service/ISSUES.md` T14-T16); `uv.lock` не внедрён |
| 1 | Eval-контур: датасет 40-60, baseline `hybrid_single` | ⬜ | каталога `eval/` нет вообще — **см. §4 «Что дальше»** |
| 1b | Langfuse self-host + CallbackHandler | ⬜ | не подключено, трейсов нет |
| 1c | Эксперимент роутера (LogReg/kNN/гибрид) | 🔶 | датасет всё ещё 3 класса (998 строк); добавлен трипваер-тест `test_ml_router_dataset_labels.py`, сам эксперимент не проводился |
| 2 | Образы rag-api/rag-worker (split requirements) | ✅ | сделано 2026-07-28 (`rag_service`, 18ГБ→2.6ГБ) |
| 2d | LLM Gateway-модуль | 🔶 | `llm_gateway.py` есть, `generate_json` реален (Pydantic+1 ретрай); fallback-цепочка между моделями не сделана (второй модели нет); Celery-задачи (аудит/суррогаты/judge) не переведены — их самих ещё нет в коде |
| 3 | Фундамент агента (контекст+injection-разделители, AgentResponse+extract_sources, no_data, SSE-отмена) | 🔶 | SSE-отмена сделана раньше (2026-07-27); `extract_sources` — реальная нода в графе; `no_data` — в графе, гейт захардкожен never-fire; **injection-разделители в build_prompt НЕ добавлены**; `AgentResponse` как отдельная модель не создана — `AskResponse` расширен аддитивными полями вместо неё |
| 4 | Rerank (второй TEI bge-reranker-v2-m3) | ✅ | развёрнуто и включено 07.2026 **без baseline из шага 1** — сознательное исключение, см. ARCHITECTURE.md §1 п.3. Живое наблюдение: top-score после реранка на реальном вопросе — 0.12 (ниже порога 0.35) → честный no_data вместо LLM-догадки по смежному контексту. Пороги требуют калибровки после появления шага 1 |
| 4b | Эксперимент LLM (T-pro vs Qwen3) | ⬜ | не приоритет, ждёт GPU-бюджета |
| 5 | Reflect (≤2 круга, 3 вердикта) | 🔶 | нода в графе, гейт захардкожен never-fire |
| 5b | Plan-ветка обобщённая (`{tool,args}` поверх реестра) | 🔶 | `resolve_docs`/`gather_passports`/`plan` — заглушки; `execute_subtasks` — **реальный диспетчер** (валидация схемы, access=="read" guard) |
| 6 | Personal (FTS заметок/задач) | 🔶 | `personal_search_node` — заглушка; `search_notes`/`search_tasks` в реестре — `NotImplementedError` |
| 7 | Post_actions + create_task/create_note/update_note | 🔶 | код-гейт (регекс-маркеры по `state.query`) — **реальный**; сама нода — заглушка; write-инструменты — `NotImplementedError` |
| 8 | Аудит ОЛ | ⬜ | не начато |
| 8b | Широкое сравнение документов как фоновый workflow | ⬜ | не начато |
| 9 | Суррогаты таблиц/рисунков | ⬜ | не начато |
| ∥P | Продукт (снять заглушку БЗ, мессенджер-фронт, backup) | 🔶 | admin-panel снесена (2026-07-22); остальное см. корневой `TODO.md` |
| ⏳ | MCP-обёртка | ⬜ | ждёт внешнего потребителя |

---

## 2. Детально по компонентам (что реально в коде сейчас)

### Граф агента (`application/lean_rag_agent.py`)

| Нода | Статус | Примечание |
|---|---|---|
| `router` → `decide_after_router` | ✅ | классы `smalltalk`/`out_of_domain`/`domain_rag` — живой трафик; `personal`/`complex` — в графе, недостижимы (роутер не переобучен) |
| `expand_queries`, `retrieve_multi`, `build_prompt`, `generate` | ✅ | без изменений, старая логика |
| `rerank` | ✅ | реально (bge-reranker-v2-m3, отдельный TEI-контейнер `tei-reranker`) — сознательное исключение из eval-ворот, см. ARCHITECTURE.md §1 п.3; ранжирует по лучшему child-чанку, не по parent_chunk |
| `decide_after_rerank` | ✅ | реальные пороги из конфига (`rerank_no_data_threshold`/`rerank_grey_zone_threshold`), не откалиброваны eval'ом |
| `decide_after_reflect` | 🔶 hardcoded | always `"sufficient"` — `reflect` (шаг 5) ещё не реализован |
| `reflect` | 🔶 | достижима (серая зона), но не улучшает выдачу — пропускает как sufficient |
| `no_data` | ✅ | достижима и реальна с 07.2026 — канонический отказ вместо LLM-галлюцинации |
| `personal_search` | 🔶 | заглушка `{"retrieval_data": []}` |
| `resolve_docs` | 🔶 | заглушка `{"resolved_docs": []}` |
| `decide_after_resolve_docs` | ✅ | реальный код-гейт (0→clarify, >max_docs_interactive→background, иначе gather_passports) — недостижим, но корректен |
| `clarify`, `background_report` | 🔶 | терминальные заглушки |
| `gather_passports` | 🔶 | заглушка `{"document_passports": []}` |
| `plan` | 🔶 | заглушка, не вызывает `llm_gateway.generate_json` (нет промпта) |
| `execute_subtasks` | ✅ | реальный диспетчер реестра, валидация по `args_schema`, отклоняет `access!="read"` |
| `decide_after_execute_subtasks` | ✅ | реальный код-гейт |
| `extract_sources` | ✅ | реальная нода (тот же `build_sources`, что раньше вызывался инлайново) |
| `decide_after_generate` | ✅ | реальный код-гейт (регекс-маркеры по `state.query`, smalltalk_ood — всегда пропуск) |
| `post_actions` | 🔶 | настоящий no-op, `proposed_action` всегда `None` |

`run_stream()` (реальный горячий SSE-путь): зеркалит только `rerank`/`extract_sources`/гейт `post_actions` (все no-op сегодня) + guard, бросающий `NotImplementedError`, если роутер когда-нибудь вернёт `personal`/`complex` — остальные новые ноды туда не зеркалятся осознанно.

### Реестр инструментов (`tool_registry.py`)

| Инструмент | access | Статус |
|---|---|---|
| `search_docs` | read | ✅ реально (оборачивает `RetrievalService.retrieve`) |
| `get_chapter` | read | ⬜ `NotImplementedError` — нет HTTP-клиента к rag_service |
| `get_document_passport` | read | ⬜ `NotImplementedError` — нет клиента к summary-эндпоинту |
| `list_documents` | read | ⬜ `NotImplementedError` |
| `search_notes`/`search_tasks` | read | ⬜ `NotImplementedError` — нет клиента к backend (заметки/задачи там) |
| `create_task`/`create_note` | write | ⬜ `NotImplementedError` |
| `update_note` | write | ⬜ `NotImplementedError` — diff-чип/optimistic lock (`note_updated_at`) не реализованы |
| `calc_gas` | read | ⬜ `NotImplementedError` |
| `run_audit` | write | ⬜ `NotImplementedError` |

### LLM Gateway (`llm_gateway.py`)

- `generate`/`generate_stream` — ✅ реально делегируют в единственный `LLMProvider`
- `generate_json(schema)` — ✅ реально (Pydantic + 1 ретрай), но **ни одна нода его не вызывает** — `plan`/`reflect`/`post_actions` без промптов
- Fallback-цепочка между моделями (`[gateway.chains]` из ARCHITECTURE.md §6) — ⬜ не реализована, второй модели/провайдера нет

### Конфиг (`ai_config.toml`)

`[gateway]` секция добавлена: `max_docs_interactive=4`, `max_subtasks=12`, `router_knn_threshold=0.15`,
`router_confidence_threshold=0.7` — используется только реальными гейтами (`decide_after_resolve_docs`),
которые сами недостижимы.

### Роутер (`ml_router/`)

`dataset.csv` — 998 строк, ровно 3 класса (`domain_rag`:531, `smalltalk`:235, `out_of_domain`:232).
Нет примеров `personal`/`complex` — граф структурно готов их принять, но роутер физически не
может их вернуть. Трипваер `tests/test_ml_router_dataset_labels.py` упадёт в день, когда датасет
переобучат — это сигнал начинать 5b/6 по-настоящему.

### Тесты

`llm_service/tests/`: 122 теста, 118 зелёных, **4 предсуществующих падения** (не из этой сессии —
`TestDecideAfterRouter::test_domain_rag_goes_to_expand_queries` и 3× `TestGenerateNode`, рассинхрон
`FinalPromptData`/тестов) — не исправлены, отдельная задача. Новые файлы: `test_tool_registry.py`,
`test_llm_gateway.py`, `test_ml_router_dataset_labels.py` + расширение `test_lean_rag_agent.py`
(байт-в-байт регрессия графа, `TestRunStreamParity`, тесты новых гейтов/нод).

---

## 3. Сделано в сессии 2026-07-28

- rag_service: образы `rag-service`/`flower` 18ГБ→2.6ГБ (multi-stage Dockerfile), `send_task` по
  имени вместо импорта воркера, гашение вебхук-шума, фикс ghost-record, B3/B10 в ISSUES.md
- nginx: `/admin` коллизия, таймауты MinIO-загрузки
- ARCHITECTURE.md: переписан под обсуждение (comparative-поиск через `plan`/`execute_subtasks`,
  модульные заметки/задачи через реестр, LLM Gateway, гейты `max_docs_interactive`/`max_subtasks`,
  `deep_dive` agent-run, эксперимент роутера)
- llm_service: весь целевой граф разложен как инертный каркас (эта сессия) — см. §2 выше подробно
- llm_service: rerank развёрнут по-настоящему (сознательное исключение из eval-ворот) — новый
  контейнер `tei-reranker` (bge-reranker-v2-m3, GPU), `RerankerService`, реальные `rerank_node`/
  `decide_after_rerank`/`no_data`, `run_stream()` синхронизирован с графом на этой ветке. По пути
  найдено и исправлено: warmup-OOM на дефолтных лимитах TEI (сужены `MAX_BATCH_TOKENS`/
  `MAX_CONCURRENT_REQUESTS` + `AUTO_TRUNCATE`), реранк по parent_chunk вместо child-чанка (раздувал
  латентность и разбавлял сигнал — поймано ревью до боевого прогона)

---

## 4. Что дальше (рекомендованный порядок)

**Следующий шаг — Шаг 1, Eval-контур.** Ничем не заблокирован (не требует GPU/железа), и является
предусловием для honest-проверки почти всего остального:
- rerank (шаг 4) явно требует baseline (см. ARCHITECTURE.md §1 п.3, добавлено в этой сессии)
- эксперимент роутера (1c) не сравнить без метрики
- включение `reflect`/`no_data` для реальных данных нельзя оценить без датасета вопросов

Конкретные первые действия:
1. `llm_service/eval/` — каталог, `run_eval.py` (сборка golden-датасета → прогон через граф → метрики)
2. Датасет 40-60 вопросов, 7 категорий + comparative (см. ARCHITECTURE.md шаг 1) — часть вопросов
   можно взять из реальных логов чата (аноним./очищенных)
3. Baseline-прогон `hybrid_single` (текущий граф как есть) → зафиксировать в `eval/runs/` с git-commit

После этого — 1b (Langfuse, одна строка CallbackHandler) параллельно, и 1c (эксперимент роутера)
на той же eval-инфраструктуре.

**Не начинать без явного решения**: 4b (эксперимент LLM, ждёт GPU-бюджета — см. ARCHITECTURE.md §6),
8/8b/9 (аудит/сравнение/суррогаты — большие фичи, после того как фундамент графа реально заработает,
не как заглушка).

---

## 5. Открытые вопросы для будущих сессий

- Куда вешать реальные промпты `plan`/`reflect`/`post_actions` — `ai_config.toml [prompts]` (тот же
  паттерн, что и остальные) или отдельная секция под JSON-контрактные ноды?
- HTTP-клиенты к rag_service (`get_chapter`/`get_document_passport`/`list_documents`) и backend
  (`search_notes`/`search_tasks`/`create_task`/`create_note`/`update_note`) — единый httpx-клиент
  по образцу `RetrievalService`, или отдельный per-tool?
- `update_note` diff-чип + optimistic lock (`note_updated_at`) — где хранить/сравнивать: backend
  отдаёт текущий `updated_at` в ответе `search_notes`, `post_actions` кладёт его в `proposed_action`?
