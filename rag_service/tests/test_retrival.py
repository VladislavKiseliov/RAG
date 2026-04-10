from rag_service.domain.retrieval import group_hits_by_parent


def test_group_hits_by_parent_returns_empty_dict_for_empty_hits():
    result = group_hits_by_parent([])

    assert result == {}


def test_group_hits_by_parent_skips_hits_without_doc_id_or_parent_id():
    hits = [
        {"payload": {}, "score": 0.9},
        {"payload": {"doc_id": "doc-1"}, "score": 0.8},
        {"payload": {"parent_id": "parent-1"}, "score": 0.7},
        {"payload": {"doc_id": "", "parent_id": "parent-1"}, "score": 0.6},
        {"payload": {"doc_id": "doc-1", "parent_id": ""}, "score": 0.5},
    ]

    result = group_hits_by_parent(hits)

    assert result == {}


def test_group_hits_by_parent_creates_one_group_for_single_hit():
    hits = [
        {
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "page_num": "2",
                "headers": {"H1": "Intro"},
            },
            "score": 0.91,
        }
    ]

    result = group_hits_by_parent(hits)

    assert ("doc-1", "parent-1") in result
    group = result[("doc-1", "parent-1")]

    assert group["doc_id"] == "doc-1"
    assert group["parent_id"] == "parent-1"
    assert group["page_num"] == "2"
    assert group["headers"] == {"H1": "Intro"}
    assert group["children"] == [
        {
            "score": 0.91,
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "page_num": "2",
                "headers": {"H1": "Intro"},
            },
        }
    ]


def test_group_hits_by_parent_groups_multiple_children_under_one_parent():
    hits = [
        {
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "page_num": "1",
                "headers": {"H1": "Section"},
            },
            "score": 0.91,
        },
        {
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
                "page_num": "1",
                "headers": {"H1": "Section"},
            },
            "score": 0.83,
        },
    ]

    result = group_hits_by_parent(hits)

    group = result[("doc-1", "parent-1")]

    assert len(group["children"]) == 2
    assert group["children"][0]["score"] == 0.91
    assert group["children"][1]["score"] == 0.83


def test_group_hits_by_parent_separates_groups_by_doc_id_and_parent_id():
    hits = [
        {
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-1",
            },
            "score": 0.91,
        },
        {
            "payload": {
                "doc_id": "doc-1",
                "parent_id": "parent-2",
            },
            "score": 0.85,
        },
        {
            "payload": {
                "doc_id": "doc-2",
                "parent_id": "parent-1",
            },
            "score": 0.77,
        },
    ]

    result = group_hits_by_parent(hits)

    assert len(result) == 3
    assert ("doc-1", "parent-1") in result
    assert ("doc-1", "parent-2") in result
    assert ("doc-2", "parent-1") in result



from types import SimpleNamespace

from rag_service.domain.retrieval import build_retrieved_items


def test_build_retrieved_items_returns_empty_list_when_rows_are_empty():
    group_hits = {
        ("doc-1", "parent-1"): {
            "children": [
                {
                    "score": 0.91,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_num": "1",
                        "headers": {"H1": "Intro"},
                    },
                }
            ]
        }
    }

    result = build_retrieved_items(
        group_hits=group_hits,
        rows=[],
    )

    assert result == []


def test_build_retrieved_items_builds_single_item():
    group_hits = {
        ("doc-1", "parent-1"): {
            "children": [
                {
                    "score": 0.91,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_num": "2",
                        "headers": {"H1": "Section"},
                    },
                }
            ]
        }
    }

    rows = [
        SimpleNamespace(
            doc_id="doc-1",
            id="parent-1",
            page_num="2",
            headers={"H1": "Section"},
            content="parent content",
        )
    ]

    result = build_retrieved_items(
        group_hits=group_hits,
        rows=rows,
    )

    assert result == [
        {
            "doc_id": "doc-1",
            "parent_id": "parent-1",
            "page_num": "2",
            "headers": {"H1": "Section"},
            "text": "parent content",
            "score": 0.91,
            "children": [
                {
                    "score": 0.91,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_num": "2",
                        "headers": {"H1": "Section"},
                    },
                }
            ],
        }
    ]


def test_build_retrieved_items_uses_best_child_score():
    group_hits = {
        ("doc-1", "parent-1"): {
            "children": [
                {
                    "score": 0.42,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_num": "1",
                        "headers": {},
                    },
                },
                {
                    "score": 0.88,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_num": "1",
                        "headers": {},
                    },
                },
            ]
        }
    }

    rows = [
        SimpleNamespace(
            doc_id="doc-1",
            id="parent-1",
            page_num="1",
            headers={},
            content="parent content",
        )
    ]

    result = build_retrieved_items(
        group_hits=group_hits,
        rows=rows,
    )

    assert result[0]["score"] == 0.88
    assert result[0]["children"][0]["score"] == 0.88
    assert result[0]["children"][1]["score"] == 0.42


def test_build_retrieved_items_skips_groups_without_matching_parent_row():
    group_hits = {
        ("doc-1", "parent-1"): {
            "children": [
                {
                    "score": 0.91,
                    "payload": {
                        "doc_id": "doc-1",
                        "parent_id": "parent-1",
                    },
                }
            ]
        }
    }

    rows = [
        SimpleNamespace(
            doc_id="doc-1",
            id="parent-2",
            page_num="1",
            headers={},
            content="other parent",
        )
    ]

    result = build_retrieved_items(
        group_hits=group_hits,
        rows=rows,
    )

    assert result == []
