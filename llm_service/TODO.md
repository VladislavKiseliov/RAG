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
- [x] Эмбеддер роутера переведён на TEI ✅ 2026-07-31 — `infrastructure.py::_build_query_router` больше не грузит `sentence-transformers`/`multilingual-e5-large` локально (torch в образе `llm_service` был не нужен ни для чего, кроме этого), теперь ходит в уже поднятый TEI (`http://tei:80`, та же модель) через новый `ml_router/tei_embedder.py::TeiSyncEmbedder` — синхронный HTTP-клиент (route() сам синхронный, вызывается через `asyncio.to_thread`). Без "query: "-префикса, как и раньше — `train.py` обучал классификатор на сыром тексте. `sentence-transformers`/`torch`/`transformers` убраны из `requirements.txt`, сборка образа ускорилась примерно в 10 раз (модель весом ~1GB больше не качается при билде)

---

## Финальный план развития агента и экосистемы (записан 2026-07-24)

Порядок фаз — по зависимостям, не обязательно по времени начала. Статус на 2026-07-27: 3.1 и 3.4 закрыты — блокер на `gatellm.ru` пропал сам, SSE подключён от `llm_service` до фронта (см. п. 3.4 ниже).

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

**3.4 SSE-стриминг** ✅ подключён 2026-07-27
- [x] Контракт событий: `status → (token|ping)* → sources → done` — `LeanRagAgent.run_stream()`, узлы `route/expand/retrieve/build_prompt` вызываются напрямую в порядке графа (у `self.app.ainvoke()` нет токен-стриминга без `astream_events`), стримится только сам LLM-вызов
- [x] `OpenAICompatLLMProvider.generate_stream()` + `GroqLLMProvider.generate_stream()` (`stream=True` в `chat.completions.create`) — оба провайдера, не только дефолтный
- [x] `POST /llm/answer/stream` (`agent_routers.py`) — `StreamingResponse`, `text/event-stream`, ошибка на любом этапе (в т.ч. после части токенов) → событие `error`, не `HTTPException` (заголовки уже ушли)
- [x] `LeanRagAgent.build_sources()` — общий маппинг `RetrieveItem → dict`, переиспользован и в `/llm/answer`, и в `/llm/answer/stream` (раньше было продублировано)
- [x] Heartbeat ✅ 2026-07-27 — между дельтами LLM пауза не ограничена сверху, добавлен `ping`-event раз в 15с простоя (`asyncio.wait_for` вокруг `generate_stream().__anext__()` в `run_stream()`), чтобы корпоративные прокси/файрволы не рвали "тихое" соединение по своему idle-таймауту (обычно 30-60с, вне нашего контроля)
- [x] `backend` (`conversation_service.py`) ✅ 2026-07-27 — `LLMClient.stream_answer()` парсит SSE от `llm_service` построчно, `ConversationService.process_message_stream()` ре-стримит на фронт и копит `answer`/`sources` по пути; сохранение сообщения ассистента + фоновый триггер саммари — уже после конца потока, не вместо него. Новый роут `POST /api/chats/{id}/messages/stream`
- [x] Фронт ✅ 2026-07-27 — `useAiChat.js`: `fetch()` + ручной парсинг `event:`/`data:` из `response.body` (не `EventSource` — тот умеет только `GET` без тела, а нужен `POST` с вопросом/`chat_id`). Сообщение ассистента растёт по токенам, `isTyping` (для «печатает…») гасится на первом токене, отдельный `isStreaming` держит инпут задизейбленным на весь ответ
- [x] `nginx` ✅ 2026-07-27 — `proxy_buffering off` на `location /api/` (без этого nginx копил весь ответ и отдавал одним куском в конце — стриминг был не виден снаружи, хотя backend уже стримил)
- DoD: юнит-тесты `tests/test_lean_rag_agent.py` (35/35 не пре-существующих) ✅; живой E2E-тест через nginx (`curl`/`httpx.stream`) — токены реально растянуты по времени (4.5-5.1с), не одним куском ✅ 2026-07-27
- Блокер `gatellm.ru` (502 при `stream=true`, см. историю до 2026-07-27) пропал сам между сессиями — перепроверено тем же repro-запросом (`google/gemini-2.5-flash-lite`, `stream: true/false`), теперь отдаёт нормальный SSE. Причина фикса на стороне шлюза неизвестна (не наш код)
- [x] **Расширенный ретрай на транзиентные 5xx** ✅ 2026-07-27 — `_stream_completion_with_retry` ретраил только `APIConnectionError`/`APITimeoutError`, реальный 502 от `gatellm.ru` (`APIStatusError`) вообще не ретраился. Добавлены `TRANSIENT_STATUS_CODES = {502, 503, 504}` — эти коды ретраятся тем же backoff, остальные 4xx/5xx (400/401/429/500 и т.д.) — нет, как и раньше
- [x] **Fallback на нестриминговый `generate()`** ✅ 2026-07-27 — если стрим упал, не отдав ни одного токена, и ретраи (в т.ч. расширенные выше) исчерпаны, `run_stream()` разово дёргает обычный (не потоковый) вызов вместо немедленной сдачи в «ответ прерван». Воспроизводит ровно тот сценарий, что уже был живьём с `gatellm.ru` (`stream=true` падал на 100% запросов, `stream=false` работал). Если частичный ответ уже показан — fallback не включается (создал бы вторую, не связанную генерацию поверх уже отданных токенов), тут поведение не изменилось. Если и fallback падает — обычная пометка с текстом ошибки
- Не сделано: HTTP/1.1 держит до 6 соединений на домен на клиенте — при нескольких открытых чатах/вкладках зависший SSE съедает одно; не актуально без TLS/HTTP2 перед nginx (`listen 80`, без `ssl`), отмечено на будущее, если добавится TLS-терминация

**3.4a Устойчивость к дисконнекту/отмене** ✅ приоритетная часть сделана 2026-07-27, остальное — DoD на будущее

Разобрано по мотивам статьи о частых причинах "зависших" LLM-бэкендов (idle-in-transaction в
Postgres, зомби-запросы, удвоенная нагрузка от ретраев клиента). Сделано сразу, не отдельным
пунктом плана — правки применились к уже работающему стримингу и к `/llm/answer`.

Сделано:
- [x] **Backend не теряет частичный ответ при дисконнекте браузера** — `ConversationService.process_message_stream()` гоняет LLM и пишет в БД в отдельной `asyncio.Task` (`self._background_tasks`), не в самом SSE-генераторе. `StreamingResponse` Starlette при разрыве клиента шлёт `CancelledError` только в генератор, который читает `asyncio.Queue` — сама задача-производитель от HTTP-scope не зависит и не отменяется, доводит генерацию до конца и сохраняет в БД, даже если слушать её уже некому. Живой тест: `timeout 1.5 curl` оборван после первого события, до БД долетел полный (не обрезанный) ответ на 40 строк.
- [x] `update_summary` (3 сессии БД) и без этой правки уже был в отдельной `asyncio.Task` (`_trigger_summary_in_background`, сделано ещё в сессии 2026-07-24) — отмена запроса физически не может прервать её посреди транзакции.
- [x] **`stream.close()` на любом пути выхода** — `_stream_completion_with_retry()` (`LLM_provider.py`): `AsyncStream` из `openai` SDK закрывает себя сам только при полном прочтении до конца (см. докстринг `.close()`), при раннем выходе (retry/`finish_reason`/исключение/отмена задачи снаружи) соединение к апстриму раньше держалось открытым до сборки мусора. Теперь `finally: await stream.close()` на каждой итерации retry-цикла. Тест `test_stream_is_closed_when_cancelled_while_waiting_for_next_chunk` воспроизводит реальный механизм отмены (`Task.cancel()` на зависшем `__anext__()`, как делает `run_stream()`), не только штатное исключение.
- [x] **`@with_cancellation` на `/llm/answer`** (адаптировано из vLLM, `llm_service/utils/cancellation.py`) — обычный (не-стриминговый) request-response сам по себе не реагирует на дисконнект в Starlette, генерация доработала бы до конца в пустоту. Слушаем `http.disconnect` напрямую через `await request.receive()`, **не** `request.is_disconnected()` — тот стабильно врёт `False` при наличии `BaseHTTPMiddleware` (баг Starlette с 0.21.0), а в `backend` такой middleware есть (`RequestLoggingMiddleware`). Живой тест: клиент с `timeout=1.0` против ответа на ~60 строк → в логах `"Client disconnected mid-request, cancelling in-flight LLM generation"`, и `Generate finished`/`Lean agent run finished` для этого запроса не появляются вообще — генерация реально прервана, не просто ушла фоном.
- [x] Проверено: нет ни одного места в проекте с `request.is_disconnected()` (грепнул `backend`+`llm_service`) — переучивать нечего, просто не заводить этот паттерн вперёд.
- [x] Нет паттерна `if disconnected: break` нигде в стриминг-цикле — везде естественная отмена через `CancelledError`/`asyncio.wait`, конкурирующих путей завершения не заводили.

DoD на будущее (пригодится при Фазе 7 "Actions" или если появится второй, отдельный стриминговый эндпоинт с write-инструментами — тогда переносить целиком):
- [ ] `send_timeout` на стриминг-соединении — «зомби-клиент» (TCP жив, но не читает буфер) не шлёт `http.disconnect` и держит слот бесконечно; сейчас у нас нет семафора/пула слотов, которым бы это грозило, но при появлении — учесть
- [ ] Флаг `completed`/`interrupted` в БД (не просто текстовая пометка в `content`, как сейчас) — чтобы отличать «клиент отвалился сразу после `done`» (норма) от реального обрыва посреди генерации для метрик; отложено — у нас пока нет вообще никакой метрики отмен, которая бы этим полем воспользовалась
- [ ] Интеграционный тест «клиент рвёт соединение на середине стрима» с проверкой `pg_stat_activity` (нет зависших `idle in transaction`) — по духу уже покрыто юнит-тестами на `stream.close()`/`generate_and_persist`, но именно прямой запрос к `pg_stat_activity` не писали

**3.4b Миграция на нативный `fastapi.sse` (`EventSourceResponse`/`ServerSentEvent`)** ✅ 2026-07-27

Оказалось, что «heartbeat из коробки» (пункт DoD выше про `sse-starlette`) не нужно ждать —
FastAPI начиная с версии, что уже стоит у `llm_service` (0.136.1), сам умеет SSE нативно, без
сторонних пакетов. Проверено чтением исходника `fastapi/routing.py`: продюсер и
keepalive-inserter — отдельные `anyio`-таски поверх `anyio.fail_after(_PING_INTERVAL)` (15с,
приватная константа фреймворка) — тот же принцип "не отменять то, что ждём", что мы городили
руками, только сделано на уровне роутинга, для ЛЮБОГО async-generator path operation с
`response_class=EventSourceResponse`, независимо от того, что внутри (ретрай, fallback, что угодно).

- [x] `agent_routers.py::answer_question_stream` — `response_class=EventSourceResponse`, эндпоинт
      сам стал async-генератором, `yield ServerSentEvent(event=..., data=...)` вместо ручных
      f-строк `f"event: ...\ndata: ...\n\n"`. Wire-формат побайтово тот же (проверено живьём) —
      backend/фронт ничего не заметили
- [x] `lean_rag_agent.py::run_stream()` — **удалена вся ручная heartbeat-машинерия**
      (`_wait_with_heartbeat`, `PING_INTERVAL_S`, `asyncio.ensure_future`/`asyncio.wait` вокруг
      токен-цикла и fallback) — теперь просто `async for delta in generate_stream(): yield ...`,
      heartbeat даже во время fallback `generate()` — забота фреймворка, не наша. Код в разы проще
- [x] `backend/services/ai/llm_client.py` — новый keep-alive от llm_service это настоящий
      SSE-комментарий (`: ping\n\n`, `fastapi.sse.KEEPALIVE_COMMENT`), а не наш старый фейковый
      named-event `event: ping` — ручной парсер на backend его раньше молча проглатывал бы, не
      долетело бы дальше llm_service→backend хопа. Добавлена ветка на строки, начинающиеся с `:`
      — ретранслируются как `("ping", {})`, дальше по цепочке (`conversation_service.py`,
      `chats_routes.py`) ничего менять не пришлось — `ping` и так проходил transparently
- [x] Тесты на ручной ping (`test_ping_sent_on_idle_...`, `test_pings_during_slow_fallback`)
      переписаны — heartbeat теперь не unit-тестируется на этом уровне (это код FastAPI, не наш),
      тесты урезаны до проверки, что пауза между дельтами/медленный fallback не ломают саму
      сборку ответа. 65/65 тестов (не пре-существующих) проходят
- Не проверено живым 15-секундным ожиданием (только чтением исходника + юнитами) — попытка
  сконструировать in-process ASGI-тест с патченным `_PING_INTERVAL` уперлась в то, что агент —
  синглтон в `app.state.container.agent`, собранный на lifespan-старте, а `httpx.ASGITransport`
  без lifespan его не проинициализирует; не стал городить обвязку ради этого
- **Backend НЕ мигрирован** — `rag_backend` на FastAPI 0.110.3, `fastapi.sse` там физически нет
  (`ModuleNotFoundError`). Апгрейд FastAPI на живом сервисе — отдельная, более рискованная задача
  (много версий разницы, потенциальные breaking changes в DI/middleware), не сделано в этом заходе

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