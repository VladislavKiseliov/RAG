from __future__ import annotations

from llm_service.eval.suites.retrieval import (
    RankedItem,
    anchor_hit,
    hit_at_k,
    mrr,
    negative_precision,
    recall_at_k,
)


def make_item(doc_id="doc1", chapter_number="1", parent_chunk="text", score=0.9) -> RankedItem:
    return RankedItem(doc_id=doc_id, chapter_number=chapter_number, parent_chunk=parent_chunk, score=score)


class TestHitAtK:
    def test_hit_when_expected_chapter_in_top_k(self):
        items = [make_item(chapter_number="2"), make_item(chapter_number="1")]
        assert hit_at_k(items, expected_doc_id="doc1", expected_chapters=["1"], k=5) is True

    def test_miss_when_expected_chapter_outside_k(self):
        items = [make_item(chapter_number="2"), make_item(chapter_number="1")]
        assert hit_at_k(items, expected_doc_id="doc1", expected_chapters=["1"], k=1) is False

    def test_miss_when_doc_id_differs(self):
        items = [make_item(doc_id="other", chapter_number="1")]
        assert hit_at_k(items, expected_doc_id="doc1", expected_chapters=["1"], k=5) is False

    def test_empty_items_is_miss(self):
        assert hit_at_k([], expected_doc_id="doc1", expected_chapters=["1"], k=5) is False


class TestMRR:
    def test_first_rank_gives_full_score(self):
        items = [make_item(chapter_number="1")]
        assert mrr(items, expected_doc_id="doc1", expected_chapters=["1"]) == 1.0

    def test_third_rank_gives_one_third(self):
        items = [make_item(chapter_number="9"), make_item(chapter_number="8"), make_item(chapter_number="1")]
        assert mrr(items, expected_doc_id="doc1", expected_chapters=["1"]) == 1.0 / 3

    def test_no_match_gives_zero(self):
        items = [make_item(chapter_number="9")]
        assert mrr(items, expected_doc_id="doc1", expected_chapters=["1"]) == 0.0


class TestRecallAtK:
    def test_full_coverage_of_multiple_expected_chapters(self):
        items = [make_item(chapter_number="1"), make_item(chapter_number="2")]
        assert recall_at_k(items, expected_doc_id="doc1", expected_chapters=["1", "2"], k=5) == 1.0

    def test_partial_coverage(self):
        items = [make_item(chapter_number="1")]
        assert recall_at_k(items, expected_doc_id="doc1", expected_chapters=["1", "2"], k=5) == 0.5

    def test_respects_k_cutoff(self):
        items = [make_item(chapter_number="9"), make_item(chapter_number="1")]
        assert recall_at_k(items, expected_doc_id="doc1", expected_chapters=["1"], k=1) == 0.0

    def test_no_expected_chapters_is_zero_not_zero_division(self):
        items = [make_item(chapter_number="1")]
        assert recall_at_k(items, expected_doc_id="doc1", expected_chapters=[], k=5) == 0.0


class TestAnchorHit:
    def test_anchor_substring_found(self):
        items = [make_item(parent_chunk="...турникетов, установленных в соответствии с пунктом 4.2.28...")]
        assert anchor_hit(items, expected_doc_id="doc1", anchor="пунктом 4.2.28", k=5) is True

    def test_anchor_not_found(self):
        items = [make_item(parent_chunk="совсем другой текст")]
        assert anchor_hit(items, expected_doc_id="doc1", anchor="пунктом 4.2.28", k=5) is False

    def test_empty_anchor_is_false(self):
        items = [make_item(parent_chunk="что угодно")]
        assert anchor_hit(items, expected_doc_id="doc1", anchor="", k=5) is False

    def test_anchor_in_wrong_doc_does_not_count(self):
        items = [make_item(doc_id="other", parent_chunk="пунктом 4.2.28")]
        assert anchor_hit(items, expected_doc_id="doc1", anchor="пунктом 4.2.28", k=5) is False


class TestNegativePrecision:
    def test_empty_result_is_honest_no_data(self):
        assert negative_precision([], threshold=0.35) is True

    def test_low_top_score_is_honest_no_data(self):
        items = [make_item(score=0.1)]
        assert negative_precision(items, threshold=0.35) is True

    def test_high_top_score_is_false_positive(self):
        items = [make_item(score=0.9)]
        assert negative_precision(items, threshold=0.35) is False