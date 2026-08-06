# LLM Service — TODO

> **Актуализировано 2026-08-06 под planner-first.** 04-08 граф агента переведён с
> ML-роутера (`route_node`/`expand_queries_node`/`retrieve_multi_node`) на planner-first
> (`plan_node`/`execute_subtasks_node`) — см. `AGENT_GRAPH_CURRENT.md`, это источник
> истины по тому, что реально исполняется живым трафиком сегодня (пофазово, построчно
> сверено с кодом). Этот файл — историческая карта решений и открытых веток, статусы
> ниже поправлены под новую архитектуру, но детали живого поведения смотри в
> `AGENT_GRAPH_CURRENT.md`, не здесь.

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
- [x] ~~Тесты — ноды `expand`/`retrieve`/`generate` покрыты (27 тестов)~~ — стейл, `expand`/`retrieve` (legacy) больше не в живом графе. Актуально 2026-08-06: `tests/test_lean_rag_agent.py` + `test_retrieval_service.py`/`test_tool_registry.py`/`test_llm_gateway.py`/`test_reranker_service.py`/`test_llm_provider_stream_retry.py`/`test_infrastructure.py` — 233 теста, живые ноды planner-first покрыты (`plan`/`execute_subtasks`/`rerank`/`reflect`/`no_data`/`build_prompt`/`generate`/`extract_sources`/`post_actions`). End-to-end через `self.app.ainvoke()`/`astream()` покрыт частично — см. `TestRunStream`/параметризованный `test_full_graph_never_touches_disabled_router_nodes`
- [x] Убрать мёртвый код: `promt/promts.py` (промпты перенесены в `ai_config.toml`, файл удалён)
- [x] Убрать мёртвый код: `agent_service.py`, `answer_service.py` — файлов больше нет в репозитории (проверено 2026-07-17, было отмечено как незавершённое — стало стейл)
- [ ] `max_tokens` есть в `ai_config.toml` (`[llm]`) и валидируется в `AppConfig`, но нигде не передаётся в `chat.completions.create()` — решение отложено намеренно, вернуться к этому позже

---

## ML-роутер (e5 + LogReg) — ОТКЛЮЧЁН ОТ ГРАФА 2026-08-04 (статус ниже — история до отключения)

**Актуально 2026-08-06:** `route_node`/`decide_after_router` больше не в `build_agent_graph()`
(живут в `legacy_disabled_nodes.py`, не удалены, но не подключены `add_node`/`add_edge`) —
заменены `plan_node` (LLM сама решает, нужен ли поиск, вместо обученного классификатора).
`_build_query_router()` в `infrastructure.py` всё ещё строит `MLQueryRouter` при старте
(best-effort, сбой не роняет сервис — см. `ISSUES.md` B4/`AGENT_GRAPH_CURRENT.md` §6.6), но
результат сегодня никем не читается — живой код на него не ссылается. Причина — временное
архитектурное решение (planner-first проще: одна LLM вместо роутера+классов), не находка о
качестве самого роутера. Пункты ниже — история строительства, до момента отключения:

- [x] Обучение/классификатор существуют (`ml_router/train.py`, `intent_model_small.pkl`)
- [x] ~~Роутер реально вызывается в проде~~ — было верно до 2026-08-04, `infrastructure.py` строит `MLQueryRouter`, но с переходом на planner-first ничто в живом графе `.route()` не вызывает
- [x] ~~Несоответствие модели эмбеддера~~ — ложная тревога (проверено 2026-07-20). `ml_router/train.py` действительно обучает на e5-small (`intent_model_small.pkl`), но `.env`/`.env.example` (`ML_ROUTER_MODEL_PATH`) указывают на `intent_model.pkl` — отдельный артефакт, обученный на e5-large (см. `ml_router/test_model.py:MODEL_NAME`), совпадает с эмбеддером в `infrastructure.py`. `train.py`/`intent_model_small.pkl` — просто старый неиспользуемый скрипт/артефакт, не риск в проде
- [x] `route_node` блокировал event loop ✅ 2026-07-20 — `.route()` вызывается через `asyncio.to_thread` в `lean_rag_agent.py`
- [x] Второй неиспользуемый `MLQueryRouter` в `application/services/query_service.py` ✅ 2026-07-22 — удалён (был мёртвым кодом с другим порогом, 0.5 вместо 0.6 в проде, вводил в заблуждение). Заодно поправлена опечатка `row_query` → `raw_query` в `QueryExpansionService.expand()` (был найден внешним код-ревью 2026-07-21, см. `rag_service/ISSUES.md`-стиль пунчлиста)
- [x] Эмбеддер роутера переведён на TEI ✅ 2026-07-31 — `infrastructure.py::_build_query_router` больше не грузит `sentence-transformers`/`multilingual-e5-large` локально (torch в образе `llm_service` был не нужен ни для чего, кроме этого), теперь ходит в уже поднятый TEI (`http://tei:80`, та же модель) через новый `ml_router/tei_embedder.py::TeiSyncEmbedder` — синхронный HTTP-клиент (route() сам синхронный, вызывается через `asyncio.to_thread`). Без "query: "-префикса, как и раньше — `train.py` обучал классификатор на сыром тексте. `sentence-transformers`/`torch`/`transformers` убраны из `requirements.txt`, сборка образа ускорилась примерно в 10 раз (модель весом ~1GB больше не качается при билде)

---

## Финальный план развития агента и экосистемы (записан 2026-07-24)

Порядок фаз — по зависимостям, не обязательно по времени начала.

**Статус на 2026-08-06:** 3.1, 3.2, 3.4, 3.4a, 3.4b, Фаза 4, Фаза 5 закрыты (частично — реализация
да, DoD-калибровка через eval нет, см. пометки у каждой). 3.3 — ветка есть, тот же
незакалиброванный порог. Фазы 6-8 — без изменений, не начаты (Фаза 6 частично готова на
уровне реестра тулов, см. ниже). Всё это реализовано НЕ через топологию, описанную в фазах
ниже буквально (`route`→`expand`→`retrieve_multi`→`rerank`→`reflect`) — граф переехал на
planner-first 2026-08-04 (`plan`→`execute_subtasks`→`rerank`→`reflect`), см. предупреждение
в начале файла и `AGENT_GRAPH_CURRENT.md`. Названия фаз/DoD ниже описывают ЦЕЛИ, которые
все были достигнуты, просто другой топологией графа, чем предполагалось 24.07.

### Фаза 3 — Фундамент агента (`llm_service/application/lean_rag_agent.py`)

**3.1 Форматирование контекста и истории** ✅ готово 2026-07-24
- [x] `_format_child_chunks_retrive_data` — убран Python-repr `headers` (было `f"Раздел {item.metadata.headers}:..."` — сырой dict в промпте) и список child-чанков со скорами (не нужен LLM). Формат: `[Документ: <source> | Раздел <title>]\n<parent_chunk>` — `title` уже содержит номер раздела впереди, `chapter_number` отдельно не дублируется (та же логика, что в `Message.jsx::formatName` на фронте)
- [x] `filename`/`document_code` в `RetrieveItemMetadata` — сделано 2026-07-24 (см. коммит `perf(chat): урезать payload истории источников + починить подпись`), поле называется `source`, проброшено `rag_service → llm_service → backend → frontend`. Теперь используется и в промпте (п. выше)
- [x] История в `expand_queries_node` — была вторая утечка repr: `state.messages` (список словарей) подставлялся напрямую в `.format(recent_history=...)`, тоже сырым Python-repr. `build_prompt_node` уже форматировал `role: content` правильно — `expand_queries_node` теперь так же
- DoD: юнит-тесты `TestFormatChildChunks`/`test_history_formatted_as_role_content_not_raw_list_repr` в `tests/test_lean_rag_agent.py` — регрессия на repr явно проверяется (`assert "{'" not in result`)

**3.2 Структурированный ответ + `extract_sources`** ✅ реализовано (другим путём, чем задумывалось)
- [x] `api/schemas.py::AskResponse { answer, sources: list[SourceItem], route, retrieval_empty, proposed_action }` — почти буквально исходно задуманная схема; `SourceItem { doc_id, parent_id, page_num, score, text, child_chunks, headers, source }` (не `SourceRef { filename, chapter_number, title, page }`, но эквивалентно — `source`/`headers.title` те же данные под другими именами)
- [x] Нода `extract_sources_node` (`application/agent/generation_nodes.py`) — `build_sources_payload(state.retrieval_data)`, строго из финального `retrieval_data`, не рассинхронизируется
- [x] Комментарий на `AskResponse.route`/`retrieval_empty`/`proposed_action` (строки 39-42 `schemas.py`) устарел — говорит "производящие ноды недостижимы", хотя `plan_node`/`no_data_node`/`post_actions_node` уже реально их заполняют с 2026-08-05 — поправить при следующей правке файла
- DoD выполнен: `tests/test_lean_rag_agent.py::TestExtractSourcesNode`; backend штатно получает `sources`

**3.3 Ветка `no_data`** ✅ ветка реализована, ⚠️ DoD (порог из eval) — не выполнен, актуальный открытый пункт
- [x] `decide_after_rerank` (`routing_decisions.py`) + `no_data_node` (`retrieval_nodes.py`) — пустой список ИЛИ top-score ниже `rerank_no_data_threshold` → `reflect_node` решает, не сразу `no_data` (изменение топологии относительно исходного плана — LLM сначала пробует переформулировать, честный отказ только после этого или сразу на `not_in_corpus`)
- [ ] Порог (`rerank_no_data_threshold`/`rerank_grey_zone_threshold`, `ai_config.toml::gateway`) — по-прежнему "на глаз", не из распределения eval-датасета. **Это САМЫЙ старый открытый пункт в этом файле** (записан здесь ещё 2026-07-24) — см. живой воспроизведённый пример провала в `AGENT_GRAPH_CURRENT.md` §6.9 (2026-08-06): высокий скор boilerplate-раздела обманул именно этот порог
- DoD не выполнен: нет eval-датасета с размеченными negative-вопросами, `negative_precision` не измерялся вживую (кроме одного ручного прогона E3, см. память сессии)

**3.4 SSE-стриминг** ✅ подключён 2026-07-27, ⚠️ механизм ниже описан устаревший (см. правку 2026-08-05)
- [x] ~~Контракт событий: `status → (token|ping)* → sources → done` — узлы `route/expand/retrieve/build_prompt` вызываются напрямую в порядке графа~~ — это был `StreamRunner` (`agent_stream.py`), императивная копия топологии графа в обход LangGraph. **Удалён 2026-08-05**: `run_stream()` теперь гоняет ТОТ ЖЕ `self.app` через `astream(stream_mode=["custom", "values"])`, что и `run()` через `ainvoke()` — ноды сами пишут в поток через `get_safe_stream_writer()` (`plan_node`/`execute_subtasks_node` — `status`, `generate_node`/`no_data_node` — `token`), не отдельный ручной раннер. Контракт событий (`status → token* → sources → done`) не изменился, изменился только механизм под ним — см. `AGENT_GRAPH_CURRENT.md` §1
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

### Фаза 4 — Rerank (пересборка контекста) ✅ реализовано 07.2026, ⚠️ DoD (eval/калибровка) не выполнен
- [x] Второй TEI-контейнер `tei-reranker` — `BAAI/bge-reranker-v2-m3`, `docker-compose.full.yml`, GPU (та же GTX 1660 Ti, что и `tei`/`rag-worker` — бюджет VRAM учтён, см. память "Admin Status + ML Router TEI Migration")
- [x] Нода `rerank_node` (`application/agent/retrieval_nodes.py`) — между `execute_subtasks_node` и `reflect`/`build_prompt` (не между `retrieve_multi` и `reflect` — `retrieve_multi_node` заменён на `execute_subtasks_node`, топология другая, суть та же)
- [x] Ранжирует по лучшему child-чанку каждого parent, не по `parent_chunk` целиком; парент-чанки не схлопываются в 1 документ (см. `AGENT_GRAPH_CURRENT.md` §2.4)
- [x] Калиброванные скоры реранкера (0..1) заменили DBSF-скоры во всех порогах (`rerank_no_data_threshold`/`rerank_grey_zone_threshold`, `no_data`/`reflect`-гейт) — сделано, но САМИ значения порогов не калиброваны (см. 3.3 выше, тот же открытый пункт)
- DoD не выполнен: eval `hybrid_rerank` vs baseline не прогонялся, латентность ноды не измерялась формально — сознательное исключение из eval-ворот (см. `AGENT_GRAPH_CURRENT.md` §2.4, "развёрнут как сознательное исключение")

### Фаза 5 — Reflect (ограниченная рефлексия) ✅ реализовано 2026-08-05, ⚠️ DoD (eval) не выполнен
- [x] Нода `reflect_node` после `rerank`, вызывается когда `decide_after_rerank` вернул `grey_zone` ИЛИ `empty` (шире исходного "top-score в серой зоне и/или мало результатов" — пустой результат тоже уходит сюда, не сразу в `no_data`)
- [x] Вердикт через `LLMGateway.generate_json` + 1 retry на невалидном JSON: `ReflectOutput { verdict: sufficient|need_more|not_in_corpus, new_queries, needs_appendix }` — структура ближе к задуманной, чем казалось (`missing` не завели — не понадобилось), модель НЕ из `[llm_summary]` (основная, не дешёвая — пересмотреть, если качество/цена станут проблемой)
- [x] Жёсткий потолок `state.reflect_rounds >= 1` → fast-path без LLM, `not_in_corpus` → `no_data_node`, `need_more` → повторный `execute_subtasks_node` по `new_queries` (в одной `search_docs`-подзадаче, см. §5.2 `AGENT_GRAPH_CURRENT.md`)
- [x] 2026-08-06: `retrieval_data` между кругами накапливается (не перезаписывается), `reflect_prompt` видит уже пробованные формулировки и их скор (`tried_queries`) — не было в исходном плане, добавлено по итогам живого разбора (см. `AGENT_GRAPH_CURRENT.md` §6.1/§2.6)
- DoD не выполнен: eval `with_reflection` vs `hybrid_rerank` не прогонялся — тот же блокер, что 3.3/Фаза 4

### Фаза 6 — Personal (поиск по заметкам и задачам) — план актуален, роутер-часть устарела
- [ ] Postgres FTS: `to_tsvector('russian', title || ' ' || content)` + GIN-индекс (миграция Alembic); `pg_trgm` + триграмный индекс
- [x] Инструменты `search_notes(query)`/`search_tasks(query)` УЖЕ зарегистрированы в `tool_registry.py` (2026-08-05) — `args_schema` готовы (`SearchNotesArgs`/`SearchTasksArgs`), `fn` — `NotImplementedError`-заглушка (не молча пустой успех). Осталось реализовать сам `fn` (HTTP-клиент к backend), схему трогать не нужно
- [ ] Identity Scope: `user_id` строго из auth-контекста сервиса, у LLM этого параметра в схеме вызова нет вообще — актуально как было
- [ ] ~~Роутер: класс `personal`, +50-100 примеров в `ml_router/data/dataset.csv`, переобучение~~ — НЕ АКТУАЛЬНО, ML-роутер отключён от графа (см. секцию выше). `plan_node` сам решает вызывать ли `search_notes`/`search_tasks` через `plan_prompt` — нужно дописать эти два тула в текст промпта (`ai_config.toml`), не переобучать классификатор
- [ ] Ветка в графе: ~~`personal → tool → build_prompt`~~ — не нужна отдельная ветка, `execute_subtasks_node` уже универсально диспетчерит любой read-тул из реестра, включая будущие `search_notes`/`search_tasks`
- DoD: тесты изоляции данных (пользователь A не находит заметки пользователя B ни при каких условиях)
- ⚠️ **Блокер `search_tasks`** не снят: бэкенда Задач на день (Фича 6 в корневом `TODO.md`) по-прежнему нет. `search_notes` можно делать независимо

### Фаза 7 — Actions (write-инструменты с подтверждением) — нода-заглушка уже в графе, планировавшийся intent-детект не сделан
- [x] Нода `post_actions_node` (`application/agent/generation_nodes.py`) уже в графе после `extract_sources_node`, достижима по code-гейту `_ACTION_MARKERS_RE` (regex по маркерам в `state.query`: "сохрани"/"закинь"/"создай задачу" и т.п., см. `AGENT_GRAPH_CURRENT.md` §2.12) — дешевле, чем "дешёвая модель определяет намерение" из исходного плана, LLM вообще не вызывается на этом шаге
- [ ] Сама нода — настоящий no-op: `return {"proposed_action": None}`, не строит `proposed_action` вообще. Ни один write-тул (`create_task`/`create_note`/`update_note`) не реализован (`NotImplementedError` в `tool_registry.py`) — вот это и есть непосредственно оставшаяся работа Фазы 7
- [ ] Исполнение только по явному подтверждению с фронта: `POST /actions/execute` — как и планировалось, не начато
- [ ] Идемпотентный ключ: `hash(message_id + action_type + action_title)` — повторный клик/ретрай не дублирует запись
- DoD: E2E — «и закинь задачей» → интерактивный чип на фронте → клик → задача с цитатами глав; повторный клик не дублирует

### Фаза 8 — AI-аудит опросных листов (= Фича 1 в корневом `TODO.md`)
Предусловие: Фазы 1-4 закрыты. Фаза 4 (rerank) реализована (см. выше) — предусловие по ней
формально выполнено, но калибровка порогов (eval, тот же блокер, что в 3.3/Фазе 4/Фазе 5)
всё ещё не сделана, так что реальная готовность к Фазе 8 не выше, чем была. Отдельный
Celery-конвейер, переиспользует `RetrievalService`/`llm_provider`, НЕ ветка графа агента.

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