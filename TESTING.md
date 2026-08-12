# TESTING.md — как в проекте устроено тестирование

Практическое руководство: архитектура тестовой инфраструктуры, как писать тест каждого уровня
с нуля, какие граничные условия проверять всегда, с чего начинать, если тестов ещё нет.
Касается `backend` и `rag_service` (Python/pytest). Оценка *качества RAG-ответов* — отдельный
контур, живёт в `llm_service/EVAL_PLAN.md` и `llm_service/eval/`, здесь не описывается.

---

## 1. Принципы

1. **DDD + TDD** (см. `CLAUDE.md`) — новая логика в доменном/application-слое покрывается тестом;
   инфраструктура спрятана за интерфейсами (`Protocol`), поэтому её можно подменить моком без
   боли.
2. **Dependency Injection через конструктор** — единственная причина, по которой unit-тесты вообще
   дёшевы в этом проекте. Если класс сам создаёт себе зависимости внутри (`self.db = Database()`),
   его нельзя протестировать без реальной базы. Если зависимости приходят в конструктор — можно
   подставить `AsyncMock()` и не поднимать вообще ничего.
3. **Форма пирамиды: много unit → меньше integration → совсем немного e2e.** Не наоборот. Если
   для проверки одной ветки `if` приходится поднимать Postgres — это неправильный уровень теста.

---

## 2. Три уровня — что каждый проверяет здесь

| Уровень | Что проверяет | Что мокается | Пример в репо | Когда писать |
|---|---|---|---|---|
| **Unit** | Логику одного класса/метода — ветвление, вычисления, вызовы зависимостей в правильном порядке | Всё вокруг (репозитории, storage, LLM-клиент — через `AsyncMock`/`MagicMock`) | `rag_service/tests/test_retrieve_service.py` | На каждую новую ветку логики в application/domain-слое |
| **Integration** | Что твой SQL/ORM/S3-код реально работает с реальной инфраструктурой, не с фантазией мока | Ничего инфраструктурного — реальный Postgres/MinIO. Мокается только то, что не относится к проверяемому слою | `rag_service/tests/test_integration_document_orchestrator.py`, `rag_service/tests/test_db/*` | На каждый repository/orchestrator, если в нём есть нетривиальный SQL (join, cascade, транзакции) |
| **E2E** | Путь целиком через HTTP: роуты, авторизацию, сериализацию, middleware, IDOR | Только внешние сервисы за границей системы (LLM-провайдер и т.п., не своя БД) | *пока нет ни одного* | На каждый подтверждённый баг с авторизацией/данными чужого пользователя, на каждый критичный пользовательский сценарий |

---

## 3. Архитектура тестовой БД

**Решение (закреплено 2026-08-07): [Testcontainers](https://testcontainers-python.readthedocs.io/),
не постоянная база рядом с прод-БД и не `docker-compose`/`services:`-блок в CI.**

### Принцип

- **Схему знают только Alembic-миграции** (`migrations/rag/`, `migrations/users/`, секции `[rag]`/`[users]`
  в корневом `alembic.ini`). Тестовый код никогда не делает `create_all`/`DROP SCHEMA` сам — это
  создаёт риск, что тестовая схема разойдётся с тем, что реально накатывает `alembic upgrade head`
  в проде.
- **Postgres поднимается кодом**, не внешней инфраструктурой. Каждый сервис поднимает **свой**
  контейнер (не делят один на двоих) — это проще, чем городить общий root-conftest между сервисами
  с разными `settings`, и ничего не стоит по ресурсам.
- **Никаких статических тестовых кредов** — host/port/user/pass генерируются на лету, `TEST_DB_*` в
  `.env` больше не нужны.

### Целевой conftest (пример для `rag_service`)

```python
# rag_service/tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from alembic.config import Config
from alembic import command

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:18") as pg:   # версия = как в проде (docker-compose.full.yml)
        yield pg

@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(pg_container):
    cfg = Config("alembic.ini", ini_section="rag")   # секция из корневого alembic.ini
    cfg.set_main_option("sqlalchemy.url", pg_container.get_connection_url())
    command.upgrade(cfg, "head")
```

`backend/tests/conftest.py` — то же самое с `ini_section="users"`.

Существующие integration-фикстуры (`engine` в `test_integration_document_orchestrator.py`,
`test_db/test_integration_database_document_service.py`, `backend/tests/conftest.py`) перестают
делать DDL сами — просто строят `engine`/`session_factory` из `pg_container.get_connection_url()`.
Seed-данные (как сейчас в `backend/tests/conftest.py` — Alice/Bob/Carol, `test_user`, `test_direct_chat`)
остаются без изменений, они не про схему.

### CI становится тривиальным

Никакого `services:`-блока, healthcheck'а или отдельного шага миграций в YAML — всё внутри фикстур:

```yaml
name: tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest   # Docker уже есть из коробки
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r rag_service/requirements.txt -r backend/requirements.txt
      - run: pytest rag_service/tests backend/tests
```

### Локально

То же самое — `pytest rag_service/tests`, при условии что Docker Desktop запущен (он и так постоянно
работает ради `docker-compose.full.yml`). Раз тесты гоняются в основном на пуш, а не в тесном
локальном цикле правка-тест, цена подъёма контейнера (~3-6 сек за сессию `pytest`, не за каждый тест)
не имеет значения.

### Почему не постоянная БД / не `services:`-блок

| | Testcontainers | Постоянная тестовая БД / `services:` |
|---|---|---|
| Движущихся частей | 1 (pytest) | 3 (внешний Postgres, скрипт подготовки, pytest) |
| Ручная подготовка | нет | нужно один раз создать БД руками, поддерживать креды в `.env` |
| Риск "забыли создать БД" | невозможен — создание физически является кодом | реален (столкнулись с этим на практике) |
| Изоляция между прогонами | идеальная — свежий контейнер каждый раз | общая БД — состояние может протечь, если забыть сброс схемы |
| Параллельные прогоны в будущем | безопасно по конструкции | гонка на `DROP SCHEMA` между воркерами |

### Текущее состояние (честно)

`rag_service` пока на `DROP SCHEMA CASCADE` + `create_all` внутри тестовых фикстур, `backend` — на
`Base.metadata.drop_all`/`create_all` против постоянной `test_myapp_db`. Миграция на testcontainers
ещё предстоит:

1. Добавить `testcontainers` в `requirements-dev`/`requirements.txt` обоих сервисов.
2. Переписать `rag_service/tests/conftest.py` и `test_db/*`/`test_integration_document_orchestrator.py`
   на `pg_container`/`alembic upgrade head` вместо `create_all`.
3. Переписать `backend/tests/conftest.py` так же (seed-фикстуры Alice/Bob и т.д. не трогать).
4. Добавить `.github/workflows/tests.yml` (см. выше).

---

## 4. Как написать unit-тест — с нуля

1. Найди класс, который меняешь/добавляешь. Посмотри его `__init__` — все зависимости приходят
   параметрами? Если внутри `__init__` что-то создаётся напрямую (не через параметр) — сначала
   вынеси это в конструктор, иначе тест невозможен без реальной инфраструктуры.
2. Замокай каждую зависимость через `AsyncMock()` (для async-методов) или `MagicMock()`.
3. Настрой моку только то поведение, которое нужно этому конкретному тесту (`mock.search =
   AsyncMock(return_value=[...])`) — не больше.
4. Вызови метод, проверь **поведение**, не внутренности: какой метод мока был вызван, с какими
   аргументами (`mock.search.assert_called_once_with(...)`), что вернул сам тестируемый метод.
5. Один тест — одна ветка логики. Если тест называется `test_retrieve_...` и проверяет три вещи
   сразу — это три теста.

Живой пример: `rag_service/tests/test_retrieve_service.py` — `RetrieveService` собирается с
`AsyncMock()`-подстановками `vector_storage`/`v_indexing_service`/`database`/`s3_storage`, тест
проверяет одну вещь: что `AbbreviationExpander.expand()` вызывается первым и его результат
(а не исходный список) определяет, идёт запрос через `search()` или `batch_search()`.

**Анти-паттерн:** мокать то, чем ты не владеешь на границе (например, замокать сам SQLAlchemy —
вместо этого мокай репозиторий, который его использует). Мокай на границе своего кода, не глубже.

---

## 5. Как написать integration-тест — с нуля

1. Нужен реальный Postgres/MinIO — фикстуры `engine`/`session_factory` уже даёт `conftest.py`
   (после перехода на testcontainers — автоматически, ничего дополнительно поднимать не нужно).
2. Данные готовятся напрямую через ORM/repository (`session.add(...)`, `insert(...)`), не через
   HTTP — integration-тест целится в слой сервиса/репозитория, HTTP выше по пирамиде.
3. Проверяй то, что не может проверить unit-тест: реальные constraints (`UNIQUE`, `FOREIGN KEY`,
   `CASCADE`), реальные транзакции, реальную сериализацию типов (`UUID`, `JSONB`, enum).
4. Каждый тест сам создаёт себе данные и сам их не обязан удалять (следующий прогон testcontainers
   даёт чистый контейнер) — но если тест внутри сессии не первый, используй уникальные ключи
   (`uuid.uuid4()` в логине/имени), не хардкоженные ID, если несколько тестов делят один `engine`.

В `backend/tests/conftest.py` уже готовы фикстуры `test_user`, `test_user_bob`, `test_ai_chat`,
`test_direct_chat`, `alice`, `bob`, изолированные обёртки над репозиториями (`chat_repository`,
`message_repository` и т.д.) — можно писать тестовые функции прямо поверх них, инфраструктура не
нужна, она уже есть и просто ничем пока не используется.

---

## 6. Как написать e2e-тест

Пока в репозитории таких нет. Когда появятся (см. §8, приоритет №1) — паттерн:

```python
from httpx import AsyncClient, ASGITransport
from backend.main import app

async def test_user_cannot_read_foreign_chat(test_user, other_user_chat):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login_as(client, test_user)
        response = await client.get(
            f"/chats/{other_user_chat.guid}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404   # не 200 и не 403 — чужой чат не должен быть виден вообще
```

Проверяется весь путь: middleware авторизации, роут, сериализация ответа — то, что unit/integration
принципиально не видят.

---

## 7. Граничные условия — что проверять всегда

Не общий чек-лист "из интернета", а то, что конкретно для этого проекта уже один раз стреляло или
структурно может выстрелить:

**Авторизация / IDOR**
- Может ли пользователь A получить чат/заметку/документ пользователя B по чужому `guid`/`id`?
  (уже находили и чинили — `backend_critical_fixes_2026_08_03`)
- Последний админ — нельзя самоудалиться/самопонизиться (`backend_security_phase0` — проверить,
  что guard реально держит границу, не только существует)
- Истёкший/невалидный JWT, отсутствующий заголовок — честная 401, не 500

**Входные данные**
- Пустая строка / только пробелы в вопросе пользователя
- Очень длинный текст (вопрос на 50к символов — что делает `plan`/`generate`?)
- Не-ASCII/русский текст на границах (уже обжигались на pymorphy3-леммах и кодировках .env —
  `rag_service_test_rewrite_2026_08_03`)
- Текст, похожий на попытку prompt injection внутри документа корпуса (уже есть grounding-защита
  в промпте — тест должен проверять именно её, не полагаться на промпт молча)

**Конкурентность**
- Два сообщения в один чат почти одновременно — `ConversationService` держит `asyncio.Lock` per
  `chat_id` на саммари намеренно (см. комментарий в коде) — тест должен проверять, что лок реально
  не даёт двум пересекающимся батчам перезаписать `summary` друг другом

**Отказ внешних сервисов**
- `llm_service` недоступен из `backend` — деградированный ответ показывается пользователю, но
  **не пишется** в историю/саммари (`b9f6b9a` в git log) — тест должен проверять именно это
- Обрыв SSE-стрима на середине генерации — частичный ответ сохраняется с пометкой, не молча теряется

**Документы / ingestion**
- Битый/повреждённый PDF — не должен ронять весь batch-процесс
- PDF без номерных заголовков — `ChapterSplitter` уже один раз падал на этом
  (`docling_false_positive_headings`)
- Повторная загрузка того же файла (совпадение `file_hash`)
- Файл пропал из S3, а запись о документе осталась — уже было (`rag_service_ingestion_robustness`)

**Пустые/граничные результаты**
- Поиск вернул 0 документов → ветка `no_data`, не выдуманный ответ
- Документ без глав/секций — читалка и summary не должны падать на `None`/пустом списке
- Ровно на границе лимита (`max_docs_interactive`, `max_subtasks`, `rerank_final_k`) — за
  единицу до и после порога, не только "типичный" случай в середине диапазона

---

## 8. С чего начинать (backend сейчас — 0 тестов, только фикстуры)

Не сверху вниз по теории пирамиды, а по тому, что уже один раз реально ломалось:

1. **E2E-регрессия на два подтверждённых бага** — chat_id в мессенджере и IDOR в AI-чате
   (`backend_critical_fixes_2026_08_03`). Баг найден, фикс есть, тест — нет. Самая высокая отдача.
2. **Unit на `ConversationService`** — уже сложная логика (фоновое саммари, lock по `chat_id`,
   `degraded`-ответы не пишутся в историю) проверяется сейчас только руками.
3. **Integration на repository-слой** — фикстуры (`alice`, `test_direct_chat`, `chat_repository`
   и т.д.) в `backend/tests/conftest.py` уже готовы, нужно только написать тестовые функции поверх
   них.

---

## 9. Definition of Done для тестов

- Новая логика в domain/application-слое → есть unit-тест на неё, не "потом допишем".
- Пофикшен баг → тест сначала воспроизводит баг (падает на старом коде), потом фиксится код —
  не наоборот, иначе нет гарантии, что тест вообще проверяет то, что нужно.
- Тест мигает (flaky) → чинится или удаляется сразу, не игнорируется молча — мигающий тест хуже,
  чем отсутствующий, он приучает не доверять красному.
