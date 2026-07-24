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

---

## Финальный план развития агента и экосистемы (записан 2026-07-24)

Порядок фаз — по зависимостям, не обязательно по времени начала. Статус на 2026-07-24: 3.1 закрыт, 3.4 реализован на стороне `llm_service`, но не подключён — заблокирован багом стриминга на `gatellm.ru` (см. п. 3.4 ниже).

### Фаза 3 — Фундамент агента (`llm_service/application/lean_rag_agent.py`)

**3.1 Форматирование контекста и истории** ✅ готово 2026-07-24
- [x] `_format_child_chunks_retrive_data` — убран Python-repr `headers` (было `f"Раздел {item.metadata.headers}:..."` — сырой dict в промпте) и список child-чанков со скорами (не нужен LLM). Формат: `[Документ: <source> | Раздел <title>]\n<parent_chunk>` — `title` уже содержит номер раздела впереди, `chapter_number` отдельно не дублируется (та же логика, что в `Message.jsx::formatName` на фронте)
- [x] `filename`/`document_code` в `RetrieveItemMetadata` — сделано 2026-07-24 (см. коммит `perf(chat): урезать payload истории источников + починить подпись`), поле называется `source`, проброшено `rag_service → llm_service → backend → frontend`. Теперь используется и в промпте (п. выше)
- [x] История в `expand_queries_node` — была вторая утечка repr: `state.messages` (список словарей) подставлялся напрямую в `.format(recent_history=...)`, тоже сырым Python-repr. `build_prompt_node` уже форматировал `role: content` правильно — `expand_queries_node` теперь так же
- DoD: юнит-тесты `TestFormatChildChunks`/`test_history_formatted_as_role_content_not_raw_list_repr` в `tests/test_lean_rag_agent.py` — регрессия на repr явно проверяется (`assert "{'" not in result`)

**3.2 Структурированный ответ + `extract_sources`**
- [ ] Pydantic `AgentResponse { answer, sources: list[SourceRef], route, retrieval_empty }`, `SourceRef { doc_id, filename, chapter_number, title, page }`
- [ ] Нода `extract_sources` — sources строго из чанков, реально попавших в `build_prompt` (не рассинхронизируется, если LLM перефразирует название СП/ГОСТа)
- [ ] Убрать мёртвое поле `sources` из логирования `run()` либо перевести на заполнение из `AgentResponse`
- DoD: тест на структуру в `tests/test_lean_rag_agent.py`; backend штатно прокидывает `sources` на фронт
- Примечание: эта структурированная схема заодно снимает блокер, зафиксированный в памяти сессии по Фиче 1 (AI-аудит опросников) — «structured-output LLM не существует нигде в проекте». Делать 3.2 раньше 8.2, не наоборот

**3.3 Ветка `no_data`**
- [ ] После `retrieve`: пустой список ИЛИ top-score ниже порога → детерминированный ответ «В базе знаний нет информации по вашему запросу», `retrieval_empty=True`, без вызова LLM
- [ ] Порог — из распределения negative-вопросов eval-датасета (Фаза 1), выносится в конфиг
- DoD: negative-вопросы датасета гарантированно идут через ветку; `negative_precision` в eval вырос

**3.4 SSE-стриминг** ⚠️ код готов 2026-07-24, НЕ подключён к чату — блокер на стороне LLM-шлюза
- [x] Контракт событий: `status → token → sources → done` — `LeanRagAgent.run_stream()`, узлы `route/expand/retrieve/build_prompt` вызываются напрямую в порядке графа (у `self.app.ainvoke()` нет токен-стриминга без `astream_events`), стримится только сам LLM-вызов
- [x] `OpenAICompatLLMProvider.generate_stream()` + `GroqLLMProvider.generate_stream()` (`stream=True` в `chat.completions.create`) — оба провайдера, не только дефолтный
- [x] `POST /llm/answer/stream` (`agent_routers.py`) — `StreamingResponse`, `text/event-stream`, ошибка на любом этапе (в т.ч. после части токенов) → событие `error`, не `HTTPException` (заголовки уже ушли)
- [x] `LeanRagAgent.build_sources()` — общий маппинг `RetrieveItem → dict`, переиспользован и в `/llm/answer`, и в `/llm/answer/stream` (раньше было продублировано)
- [ ] `backend` (`conversation_service.py`) — проксирование потока на фронт + сохранение сообщения по `done` — **не сделано, ждём фикса шлюза**
- [ ] Фронт — консюмер SSE в `useAiChat.js` — не сделано
- DoD: юнит-тесты `tests/test_lean_rag_agent.py` (35/35 не пре-существующих) ✅; интеграционный тест на порядок событий в БД — не сделано (нет смысла, пока backend не подключён)
- **🛑 Блокер**: `gatellm.ru` (`LLM_BASE_URL`) не умеет релеить SSE от OpenRouter — при `stream=true` возвращает `HTTP 502, Content-Type: application/json`, тело — `"OpenRouter returned non-JSON response: ..."` с сырыми SSE-байтами OpenRouter внутри строки-сообщения об ошибке. Проверено 2026-07-24 сырым `httpx` в обход `openai` SDK и нашего кода — воспроизводится на 3 разных моделях (`openai/gpt-oss-120b`, `deepseek/deepseek-v4-flash`, и даже `openai/gpt-4o-mini` — модель из официального примера в документации gatellm.ru). Не модель-специфично, не SDK-специфично — баг на стороне шлюза в релее SSE от OpenRouter. Repro-curl для тикета в поддержку gatellm.ru есть в истории сессии. Нестриминговый `/llm/answer` тем же способом работает нормально
- Примечание: как только шлюз починит стриминг (или сменится провайдер) — это настоящий фикс проблемы «долгий ответ = ошибка в чате», которую 2026-07-24 залатали временно через `nginx proxy_read_timeout 120s` (см. коммит `fix(backend,nginx): ответ чата не должен зависеть от таймаута саммари`). Подключение — пара строк в `conversation_service.py`, вся тяжёлая часть на стороне `llm_service` уже готова

### Фаза 4 — Rerank (пересборка контекста)
- [ ] Второй TEI-контейнер: `--model-id BAAI/bge-reranker-v2-m3`, эндпоинт `/rerank` (GPU, ~1.5GB VRAM)
- [ ] Нода `rerank` между `retrieve_multi` и `reflect`/`build_prompt`
- [ ] Топ 20-30 child-чанков → rerank → пересборка родителей по новым скорам, дедупликация родительских чанков (не схлопывать выборку в 1 документ)
- [ ] Калиброванные скоры реранкера (0..1) заменяют DBSF-скоры во всех порогах (`no_data`, будущий гейт `reflect`)
- DoD: eval `hybrid_rerank` vs baseline (`--compare`); латентность ноды ≤200мс; `rerank_no_expansion` — повторный прогон
- ⚠️ **Бюджет VRAM**: сейчас одна GTX 1660 Ti (6GB) уже делит TEI (эмбеддинги) и Docling (OCR/layout — GPU туда вернули 2026-07-24, см. `fix(rag_service): ChapterSplitter дублирует номера глав + GPU для Docling`). Третий потребитель на ту же карту — посчитать бюджет VRAM заранее, не по факту OOM

### Фаза 5 — Reflect (ограниченная рефлексия)
- [ ] Нода `reflect` после `rerank`, вызывается только если top-score реранкера в «серой зоне» и/или мало результатов
- [ ] Вердикт через Pydantic + 1 retry: `{"status": "sufficient|need_more|not_in_corpus", "missing": str, "new_queries": list[str]}`, лёгкая модель из `[llm_summary]`
- [ ] Жёсткий потолок: `iteration >= 2` → принудительно в `generate`. `not_in_corpus` → в `no_data`. `need_more` → повторный `retrieve` по `new_queries`
- DoD: eval `with_reflection` vs `hybrid_rerank` — прирост на cross_chapter/abbrev без деградации p95 на простых запросах; тест на потолок итераций

### Фаза 6 — Personal (поиск по заметкам и задачам)
- [ ] Postgres FTS: `to_tsvector('russian', title || ' ' || content)` + GIN-индекс (миграция Alembic); `pg_trgm` + триграмный индекс
- [ ] Инструменты `search_notes(query)`, `search_tasks(query)`
- [ ] Identity Scope: `user_id` строго из auth-контекста сервиса, у LLM этого параметра в схеме вызова нет вообще
- [ ] Роутер: класс `personal`, +50-100 примеров в `ml_router/data/dataset.csv`, переобучение
- [ ] Ветка в графе: `personal → tool → build_prompt`
- DoD: тесты изоляции данных (пользователь A не находит заметки пользователя B ни при каких условиях); приемлемая confusion-матрица роутера на новом классе
- ⚠️ **Блокер `search_tasks`**: бэкенда Задач на день (Фича 6 в корневом `TODO.md`) пока нет вообще — «новый домен, бэкенда нет». `search_notes` можно делать независимо, `search_tasks` ждёт

### Фаза 7 — Actions (write-инструменты с подтверждением)
- [ ] Нода `post_actions` после `extract_sources` — дешёвая модель определяет намерение («сохрани как задачу») → `proposed_action` в `AgentResponse` (title из вопроса, body = ответ + sources). Сам инструмент НЕ исполняется на этом шаге
- [ ] Исполнение только по явному подтверждению с фронта: `POST /actions/execute`
- [ ] Идемпотентный ключ: `hash(message_id + action_type + action_title)` — повторный клик/ретрай не дублирует запись
- DoD: E2E — «и закинь задачей» → интерактивный чип на фронте → клик → задача с цитатами глав; повторный клик не дублирует

### Фаза 8 — AI-аудит опросных листов (= Фича 1 в корневом `TODO.md`)
Предусловие: Фазы 1-4 закрыты. Отдельный Celery-конвейер, переиспользует `RetrievalService`/`llm_provider`, НЕ ветка графа агента.

- [ ] **8.1 Ingestion & Payload** — нормализация обозначений документов при инжесте (СП 62.13330.2011 + вариации → канонический вид), поле `document_code` (+редакция) в Payload, Payload-индекс в Qdrant, `search_in_document`
- [ ] **8.2 JSON-промпт инспектора** — статусы `OK|WARNING|VIOLATION|NO_DATA` (`NO_DATA` обязателен, если норматив не найден), дословная цитата + nullable-ссылка на пункт, пересчёт единиц (давление/температура) — детерминированно кодом (`pint`), не LLM
- [ ] **8.3 Two-Pass RAG** — Pass 1: Qdrant Payload Filter по документам из шапки ОЛ. Pass 2: по всему корпусу ГОСТов — коллизии/противоречия
- [ ] **8.4 Полнота ОЛ** — чек-лист обязательных полей на основе `chapter_summaries`
- [ ] **8.5 Excel-отчёт** (`openpyxl`) — `.xlsx`, лист Dashboard + реестр замечаний, цвет (зелёный/жёлтый/красный/серый для NO_DATA — «требует ручного контроля»)
- [ ] **8.6 Валидация & UX** — 2-3 реальных ОЛ с вручную внесёнными нарушениями + разметка ожидаемых вердиктов; позиционирование «система предлагает, выбор за инженером»; фоновая Celery-задача PENDING→PROCESSING→COMPLETED, 3-10 мин

### 🚀 Параллельная продуктовая линия (независимо от Фаз 2-8)
- [ ] **P1** — снять in-memory заглушку базы знаний в backend (`stub_routes.py`), довести knowledge-proxy до `rag_service` (тот же пункт уже есть в корневом `TODO.md`, Фаза 2 «Достроить то, что фронт уже показывает»)
- [ ] **P2** — доделать фронтенд мессенджера (фича остаётся в продукте). Вынос в `messenger_service` — строго по триггеру «деплои backend рвут активные сокеты реальным пользователям», не раньше
- [x] **P3** — удалить legacy `admin-panel/` ✅ уже сделано 2026-07-22 (см. корневой `TODO.md`)

### 🛑 Отложено осознанно (не делать без отдельного архитектурного решения)
- CQRS-разделение ingestion/retrieval по разным микросервисам
- Вынос модуля авторизации (auth)
- Вынос router/expansion в отдельные сервисы
- Отдельная Qdrant-коллекция для заметок (пока полностью закрывается Postgres FTS + Trigram)
- Свободный ReAct-цикл без жёсткого потолка итераций