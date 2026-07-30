from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.document import DocItemLabel, DoclingDocument, SectionHeaderItem
from docling_core.types.doc.page import (
    BoundingRectangle,
    PdfCellRenderingMode,
    PdfPageBoundaryType,
    PdfPageGeometry,
    PdfTextCell,
    SegmentedPdfPage,
)

from rag_service.infrastructures.repositories.docling_conversion_repository import (
    _demote_false_positive_headings,
    _has_non_heading_series_neighbor,
    _is_bold_heading,
    _parse_number,
)

_PAGE_HEIGHT = 800.0


def make_page(cells: list[PdfTextCell]) -> SegmentedPdfPage:
    full_page_bbox = BoundingBox(l=0, t=0, r=600, b=_PAGE_HEIGHT)
    geometry = PdfPageGeometry(
        angle=0,
        rect=BoundingRectangle.from_bounding_box(full_page_bbox),
        boundary_type=PdfPageBoundaryType.CROP_BOX,
        art_bbox=full_page_bbox,
        bleed_bbox=full_page_bbox,
        crop_bbox=full_page_bbox,
        media_bbox=full_page_bbox,
        trim_bbox=full_page_bbox,
    )
    return SegmentedPdfPage(dimension=geometry, textline_cells=cells, char_cells=[], word_cells=[])


def make_cell(text: str, font_name: str, top: float, height: float = 10.0) -> PdfTextCell:
    bbox = BoundingBox(l=50, t=top, r=250, b=top + height)
    return PdfTextCell(
        rect=BoundingRectangle.from_bounding_box(bbox),
        text=text,
        orig=text,
        rendering_mode=PdfCellRenderingMode.FILL_TEXT,
        widget=False,
        font_key="F1",
        font_name=font_name,
    )


def make_heading(document: DoclingDocument, text: str, top: float, page_no: int = 1) -> SectionHeaderItem:
    bbox = BoundingBox(l=50, t=top, r=250, b=top + 10.0)
    return document.add_heading(text=text, level=2, prov=_prov(page_no, bbox))


def _prov(page_no: int, bbox: BoundingBox):
    from docling_core.types.doc.document import ProvenanceItem

    return ProvenanceItem(page_no=page_no, bbox=bbox, charspan=(0, 0))


class TestIsBoldHeading:
    def test_bold_font_name_is_bold(self):
        document = DoclingDocument(name="test")
        heading = make_heading(document, "4.2 Раздел", top=100)
        page = make_page([make_cell("4.2 Раздел", "TimesNewRoman,Bold", top=100)])

        assert _is_bold_heading(heading, {1: page}) is True

    def test_regular_font_name_is_not_bold(self):
        document = DoclingDocument(name="test")
        heading = make_heading(document, "4.2.3 Пункт", top=100)
        page = make_page([make_cell("4.2.3 Пункт", "TimesNewRoman", top=100)])

        assert _is_bold_heading(heading, {1: page}) is False

    def test_no_parsed_page_for_prov_returns_none(self):
        document = DoclingDocument(name="test")
        heading = make_heading(document, "4.2 Раздел", top=100)

        assert _is_bold_heading(heading, {}) is None

    def test_no_overlapping_cells_returns_none(self):
        document = DoclingDocument(name="test")
        heading = make_heading(document, "4.2 Раздел", top=100)
        page = make_page([make_cell("Другой текст", "TimesNewRoman", top=500)])

        assert _is_bold_heading(heading, {1: page}) is None


class TestDemoteFalsePositiveHeadings:
    def test_demotes_non_bold_heading_to_text(self):
        document = DoclingDocument(name="test")
        make_heading(document, "4.2.3 Ложный заголовок", top=100)
        page = make_page([make_cell("4.2.3 Ложный заголовок", "TimesNewRoman", top=100)])

        _demote_false_positive_headings(document, {1: page})

        assert all(not isinstance(item, SectionHeaderItem) for item in document.texts)
        assert document.texts[0].label == DocItemLabel.TEXT
        assert document.texts[0].text == "4.2.3 Ложный заголовок"

    def test_keeps_bold_heading_as_section_header(self):
        document = DoclingDocument(name="test")
        make_heading(document, "4.2 Настоящий заголовок", top=100)
        page = make_page([make_cell("4.2 Настоящий заголовок", "TimesNewRoman,Bold", top=100)])

        _demote_false_positive_headings(document, {1: page})

        assert isinstance(document.texts[0], SectionHeaderItem)

    def test_keeps_heading_when_style_undetermined(self):
        """Нет parsed_page/ячеек под bbox - не трогаем заголовок, а не считаем его ложным."""
        document = DoclingDocument(name="test")
        make_heading(document, "4.2 Заголовок", top=100)

        _demote_false_positive_headings(document, {})

        assert isinstance(document.texts[0], SectionHeaderItem)

    def test_empty_parsed_pages_is_noop(self):
        document = DoclingDocument(name="test")
        make_heading(document, "4.2 Заголовок", top=100)

        _demote_false_positive_headings(document, {})

        assert len(document.texts) == 1
        assert isinstance(document.texts[0], SectionHeaderItem)

    def test_bold_heading_demoted_by_neighbor_signal_alone(self):
        """Реальный случай: "3.25" в СП 2.13130 - жирный (шрифт не триггерит), но
        сосед по серии "3.24" - обычный текст. OR-логика: neighbor-сигнал один
        должен демоутить, даже когда font-сигнал молчит."""
        document = DoclingDocument(name="test")
        make_text(document, "3.24 Простенок: обычный текст пункта.", top=90)
        make_heading(document, "3.25 Комбинированный способ", top=100)
        page = make_page([
            make_cell("3.24 Простенок: обычный текст пункта.", "TimesNewRoman", top=90),
            make_cell("3.25 Комбинированный способ", "TimesNewRoman,Bold", top=100),
        ])

        _demote_false_positive_headings(document, {1: page})

        assert all(not isinstance(item, SectionHeaderItem) for item in document.texts)


def make_text(document: DoclingDocument, text: str, top: float, page_no: int = 1):
    from docling_core.types.doc.document import DocItemLabel as _Label

    bbox = BoundingBox(l=50, t=top, r=250, b=top + 10.0)
    return document.add_text(label=_Label.TEXT, text=text, prov=_prov(page_no, bbox))


class TestParseNumber:
    def test_two_segment_number(self):
        assert _parse_number("3.25 комбинированный способ") == (3, 25)

    def test_three_segment_number(self):
        assert _parse_number("6.10.1 Общие положения") == (6, 10, 1)

    def test_plain_text_returns_none(self):
        assert _parse_number("обычный текст без номера") is None


class TestHasNonHeadingSeriesNeighbor:
    def test_text_neighbor_before_triggers_true(self):
        """3.24 (текст) перед 3.25 (заголовок) - реальный случай СП 2.13130."""
        document = DoclingDocument(name="test")
        make_text(document, "3.24 Простенок текст пункта.", top=90)
        make_heading(document, "3.25 Комбинированный способ", top=100)
        texts = list(document.texts)

        assert _has_non_heading_series_neighbor(texts, index=1, number=(3, 25)) is True

    def test_both_neighbors_are_headings_returns_false(self):
        """6.10.1/6.10.2/6.10.3 - настоящая последовательность подглав, СП 4.13130."""
        document = DoclingDocument(name="test")
        make_heading(document, "6.10.1 Общие положения", top=80)
        make_heading(document, "6.10.2 Требования к генплану", top=90)
        make_heading(document, "6.10.3 Сырьевые склады", top=100)
        texts = list(document.texts)

        assert _has_non_heading_series_neighbor(texts, index=1, number=(6, 10, 2)) is False

    def test_no_series_neighbors_at_all_returns_false(self):
        document = DoclingDocument(name="test")
        make_heading(document, "4.2 Единственный заголовок", top=100)
        texts = list(document.texts)

        assert _has_non_heading_series_neighbor(texts, index=0, number=(4, 2)) is False

    def test_first_in_series_with_heading_after_returns_false(self):
        """6.10.1 первый в своей серии - нет "до", "после" - заголовок (6.10.2)."""
        document = DoclingDocument(name="test")
        make_heading(document, "6.10.1 Общие положения", top=90)
        make_heading(document, "6.10.2 Требования к генплану", top=100)
        texts = list(document.texts)

        assert _has_non_heading_series_neighbor(texts, index=0, number=(6, 10, 1)) is False

    def test_first_in_series_with_text_after_returns_true(self):
        document = DoclingDocument(name="test")
        make_heading(document, "6.10.1 Ложный заголовок", top=90)
        make_text(document, "6.10.2 обычный текст пункта.", top=100)
        texts = list(document.texts)

        assert _has_non_heading_series_neighbor(texts, index=0, number=(6, 10, 1)) is True
