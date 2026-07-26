from pathlib import Path
from src.style_resolver import (
    StyleProfileResolver,
)

def test_resolver_applies_manual_overrides(
    tmp_path: Path,
) -> None:
    resolver = StyleProfileResolver(
        profiles_dir=tmp_path
    )

    detected_profile = {
        "body": {
            "font": "Arial",
            "font_size": 11.0,
        },
        "source_files": [
            "reference.pdf"
        ],
        "source_file_count": 1,
    }

    overrides = {
        "body": {
            "font": "Calibri",
            "font_size": 12.0,
        },
        "page": {
            "margin_left": 60.0,
        },
    }

    resolved = resolver.resolve(
        detected_profile,
        overrides,
    )

    assert resolved["body"]["font"] == "Calibri"
    assert resolved["body"]["font_size"] == 12.0
    assert resolved["page"]["margin_left"] == 60.0

    assert resolved["source_files"] == [
        "reference.pdf"
    ]

    assert (
        resolved["resolution"]
        ["manual_overrides_applied"]
        is True
    )

    required_sections = (
        "page",
        "body",
        "title",
        "heading_1",
        "heading_2",
        "heading_3",
        "bullet",
    )

    for section in required_sections:
        assert section in resolved

def test_resolver_enforces_heading_size_order(
    tmp_path: Path,
) -> None:
    resolver = StyleProfileResolver(
        profiles_dir=tmp_path
    )

    resolved = resolver.resolve(
        detected_profile={
            "body": {
                "font_size": 12.0,
            }
        },
        overrides={
            "title": {
                "font_size": 10.0,
            },
            "heading_1": {
                "font_size": 10.0,
            },
            "heading_2": {
                "font_size": 10.0,
            },
            "heading_3": {
                "font_size": 10.0,
            },
        },
    )

    assert (
        resolved["title"]["font_size"]
        > resolved["heading_1"]["font_size"]
    )

    assert (
        resolved["heading_1"]["font_size"]
        > resolved["heading_2"]["font_size"]
    )

    assert (
        resolved["heading_2"]["font_size"]
        > resolved["heading_3"]["font_size"]
    )

    assert (
        resolved["heading_3"]["font_size"]
        >= resolved["body"]["font_size"]
    )