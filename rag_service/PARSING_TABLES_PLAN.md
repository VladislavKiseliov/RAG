# Парсинг PDF и обработка таблиц — план улучшений

## Статус на 2026-07-17

| Шаг плана | Статус | Комментарий |
|---|---|---|
| Docling-парсер | ✅ Готово | реализован, заменил pymupdf4llm |
| Изоляция таблиц + маркеры вместо inline | ✅ Готово (другой механизм) | не отдельный `extract_tables(markdown)`-regex как в плане, а `_LinkingTableSerializer` (`infrastructures/repositories/docling_conversion_repository.py:31-114`), который сразу при сериализации вставляет `[→ Таблица N](tables/...)` — устойчивее к рассинхрону, но архитектурно отличается от текста плана ниже |
| LLM-саммари по таблицам | ❌ Не сделано | кода генерации саммари нет, `document_tables` не имеет поля под него |
| Parent-child chunking | ✅ Готово | `ingestion_service.py:305-341`, `domain/chunking/chunk_builder.py` |
| **Сборка ответа: подстановка таблицы обратно при retrieval** | ❌ **Не сделано — самый существенный разрыв плана** | Реконструкция таблицы (снять маркер → достать CSV/HTML → вставить) реализована **только** в `GET /documents/{doc_id}/chapters/{n}` — human-facing эндпоинт читалки (`api/rag_routes.py:274-286`). В реальном retrieval-пути, которым пользуется `llm_service` (`application/retrieve_service.py:246-284`, `build_retrieved_items`), `row.content` отдаётся как есть — маркеры `[→ Таблица N]` остаются неразрешёнными в тексте, который видит LLM. То есть таблицы извлекаются и хранятся правильно, но **не попадают в ответы ассистента**. |

---

## Выбор парсера: Docling (IBM Research)

| Критерий | Docling 🏆 | Marker | LiteParse (LlamaIndex) |
|---|---|---|---|
| Технология | TableFormer (ИИ) + ИИ-сегментация | LayoutLM + тяжёлые веса | PDFium + базовые алгоритмы |
| Качество таблиц | Отличное, видит сложные многострочные ячейки | Очень высокое, чёткие границы | Среднее, только явная сетка |
| Формулы | Базовый текст | LaTeX (отлично) | Не поддерживает |
| Нагрузка на сервер | Низкая/Средняя, работает на CPU | Высокая, нужен GPU/NVIDIA | Минимальная |
| Форматы входа | PDF, DOCX, PPTX, XLSX, HTML | Только PDF | Только PDF |
| Лицензия | MIT | GPL-3.0 / Коммерческая | MIT |

**Почему Docling для MVP:**
- TableFormer обучена только на геометрии таблиц — ИИ-точность без GPU
- На выходе чистый Markdown с корректными заголовками (`#`, `##`) — критично для иерархического чанкинга
- MIT лицензия — нет ограничений на использование

---

## Архитектура: Parent-Child Chunking с изоляцией таблиц

**Проблема стандартного RAG:** таблицы в векторной базе превращаются в кашу из `|` и цифр, что ломает семантический поиск.

**Решение:** разделить пути хранения и пути поиска.

---

### Пайплайн (Celery воркер)

```
PDF
 │
 ▼
[1] Docling → единый Markdown
              (таблицы как текст: | ячейка |)
 │
 ▼
[2] Фильтр таблиц
    ├── Таблицы → вырезать → сохранить в Postgres (document_tables)
    └── Вместо таблицы вставить маркер: [[TABLE_REF_42]]
 │
 ▼
[3] LLM генерирует саммари для каждой таблицы
    Пример: "Сравнительная таблица времени отклика STM32 при частоте PWM..."
 │
 ▼
[4] Parent-Child чанкинг
    ├── Родительские чанки: разделы + подразделы + маркеры [[TABLE_REF_N]]
    └── Детские чанки (в Qdrant): мелкий текст + саммари таблиц
```

---

### Сборка ответа (Retrieval)

```
Вопрос пользователя
 │
 ▼
Qdrant находит детский чанк (саммари таблицы или текст)
 │
 ▼
Бэкенд достаёт родительский чанк по parent_id
 │
 ▼
Видит маркер [[TABLE_REF_42]] в тексте родителя
 │
 ▼
SELECT из Postgres → оригинальная Markdown-таблица
 │
 ▼
Вставляет таблицу вместо маркера → передаёт в LLM
 │
 ▼
LLM получает полный контекст: текст + структура таблицы
```

---

### Новая таблица в Postgres: `document_tables`

```sql
CREATE TABLE document_tables (
    id          SERIAL PRIMARY KEY,
    doc_id      UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ref_id      INTEGER NOT NULL,          -- номер маркера [[TABLE_REF_N]]
    content     TEXT NOT NULL,             -- оригинальный Markdown таблицы
    summary     TEXT,                      -- саммари от LLM для поиска
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

### Что нужно изменить в коде

**`rag_service/domain/chunking/document_parser.py`**
- Заменить текущий парсер на Docling
- Добавить шаг изоляции таблиц: `extract_tables(markdown) -> (clean_text, tables)`

**`rag_service/workers/ingestion_service.py`**
- После парсинга: сохранить таблицы в `document_tables`
- Передать `clean_text` (с маркерами) дальше в чанкинг

**`rag_service/application/retrieve_service.py`**
- После получения родительского чанка: найти маркеры `[[TABLE_REF_N]]`
- Сделать запрос в Postgres, вставить Markdown таблиц

**`rag_service/infrastructure.py`**
- Добавить репозиторий `DocumentTableRepository`

---

### Зависимости

```
pip install docling
```

Docling тянет свои модели при первом запуске (~500MB). В Docker-образе лучше
скачать заранее через `RUN python -c "from docling.document_converter import DocumentConverter"`.