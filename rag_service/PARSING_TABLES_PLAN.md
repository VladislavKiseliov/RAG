# Парсинг PDF и таблицы — живой остаток

Парсер — Docling (заменил pymupdf4llm), таблицы изолируются маркерами `[→ Таблица N]` через
`_LinkingTableSerializer` (`infrastructures/repositories/docling_conversion_repository.py`), не через
отдельный `extract_tables(markdown)`-regex, как задумывалось изначально — устойчивее к рассинхрону.
Parent-child chunking готов (`ingestion_service.py`, `domain/chunking/chunk_builder.py`).

Живой чеклист (главный разрыв пайплайна) — в `TODO.md` (Фаза 1: таблицы не долетают до ответов
ассистента, `retrieve_service.build_retrieved_items` отдаёт текст с неразрешёнными маркерами).

## Сделано

- [x] LLM-саммари по таблицам ✅ 2026-07-31 — `document_tables.summary` заполняется через
      `POST /llm/table-summary`, плюс саммари эмбеддится и упсертится в Qdrant отдельной точкой
      поверх маркера `[→ Таблица N]` (раньше содержимое таблиц было невидимо для семантического
      поиска). Подробности — `rag_service/ISSUES.md`, A10. Живой прогон выполнен на реальном
      документе — запрос по данным из таблицы находит именно её и возвращает развёрнутую таблицу.