from app.utils.json_utils import strip_empty_sections


def test_strip_empty_sections_preserves_meaningful_falsy_values():
    source = {
        "drop_none": None,
        "drop_text": "",
        "drop_list": [],
        "drop_object": {"nested": None},
        "keep_false": False,
        "keep_zero": 0,
        "keep": [{"drop": "", "visible": False}, {}, ""],
    }
    assert strip_empty_sections(source) == {
        "keep_false": False,
        "keep_zero": 0,
        "keep": [{"visible": False}],
    }


def test_strip_empty_sections_reports_removed_paths():
    removed = []

    result = strip_empty_sections(
        {"empty": "", "nested": {"gone": None, "keep": 0}, "items": [{}, "ok"]},
        removed=removed,
    )

    assert result == {"nested": {"keep": 0}, "items": ["ok"]}
    assert removed == [
        {"path": "/empty", "value": ""},
        {"path": "/nested/gone", "value": None},
        {"path": "/items/0", "value": {}},
    ]


def test_strip_empty_sections_reports_container_emptied_by_cleaning():
    removed = []

    assert strip_empty_sections({"section": {"value": ""}}, removed=removed) == {}
    assert removed == [
        {"path": "/section/value", "value": ""},
        {"path": "/section", "value": {}},
    ]
