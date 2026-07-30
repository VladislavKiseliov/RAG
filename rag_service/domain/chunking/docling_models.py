from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SavedTable:
    """Таблица, прошедшая фильтр по размеру и получившая глобальный номер."""

    index: int
    csv_bytes: bytes
    html_bytes: bytes


@dataclass(frozen=True)
class ConversionOutput:
    """Результат конвертации PDF докингом: markdown с уже подставленными
    ссылками вместо таблиц + сами таблицы, готовые к сохранению."""

    markdown: str
    tables: list[SavedTable] = field(default_factory=list)
    page_count: int | None = None


@dataclass(frozen=True)
class Chapter:
    number: str
    title: str
    markdown: str


@dataclass(frozen=True)
class MetaSection:
    section_type: str  # "TOC" | "ABBREVIATIONS" | "APPENDICES"
    markdown: str


@dataclass(frozen=True)
class ParsedDocument:
    """Итоговый результат всего пайплайна — то, что получает вызывающий код."""

    full_markdown: str
    chapters: list[Chapter] = field(default_factory=list)
    meta_sections: list[MetaSection] = field(default_factory=list)
    tables: list[SavedTable] = field(default_factory=list)
    page_count: int | None = None