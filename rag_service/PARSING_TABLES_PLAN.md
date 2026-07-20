# Парсинг PDF и таблицы — живой остаток

Парсер — Docling (заменил pymupdf4llm), таблицы изолируются маркерами `[→ Таблица N]` через
`_LinkingTableSerializer` (`infrastructures/repositories/docling_conversion_repository.py`), не через
отдельный `extract_tables(markdown)`-regex, как задумывалось изначально — устойчивее к рассинхрону.
Parent-child chunking готов (`ingestion_service.py`, `domain/chunking/chunk_builder.py`).

Живой чеклист (главный разрыв пайплайна) — в `TODO.md` (Фаза 1: таблицы не долетают до ответов
ассистента, `retrieve_service.build_retrieved_items` отдаёт текст с неразрешёнными маркерами).

## Не сделано, ещё нигде не отслежено

- [ ] LLM-саммари по таблицам — `document_tables.summary`/`document_chapters.summary` существуют как
      колонки, но никогда не заполняются