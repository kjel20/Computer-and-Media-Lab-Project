import pytest
from src.content_quality import ContentQualityValidator

def create_good_notes() -> dict:
    return {
        "title": "Database Normalization",
        "subtitle": "",
        "sections": [
            {
                "heading": "First Normal Form",
                "paragraphs": [
                    (
                        "First normal form requires every field "
                        "to contain one atomic value."
                    )
                ],
                "bullets": [
                    {
                        "text": (
                            "Each field contains one value."
                        ),
                        "children": [],
                    }
                ],
                "definitions": [
                    {
                        "term": "Atomic value",
                        "definition": (
                            "is one indivisible piece of data."
                        ),
                    }
                ],
                "examples": [],
            }
        ],
        "summary": [
            (
                "First normal form prevents multiple values "
                "from being stored in one field."
            )
        ],
    }

def test_good_notes_pass_quality_validation() -> None:
    validator = ContentQualityValidator()

    result = validator.evaluate(
        create_good_notes()
    )

    assert result["passed"] is True
    assert result["errors"] == []
    assert result["score"] > 0

def test_placeholder_example_fails_validation() -> None:
    validator = ContentQualityValidator()
    notes = create_good_notes()

    notes["sections"][0]["examples"] = [
        "Example"
    ]

    result = validator.evaluate(notes)

    assert result["passed"] is False

    assert any(
        "placeholder" in error.lower()
        for error in result["errors"]
    )

def test_require_usable_raises_for_placeholder_content() -> None:
    validator = ContentQualityValidator()
    notes = create_good_notes()

    notes["sections"][0]["bullets"] = [
        {
            "text": "Main bullet",
            "children": [],
        }
    ]

    with pytest.raises(ValueError):
        validator.require_usable(notes)