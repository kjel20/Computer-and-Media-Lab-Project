from src.note_schema import NoteSchema

def create_valid_notes() -> dict:
    return {
        "title": "Database Normalization",
        "subtitle": "",
        "sections": [
            {
                "heading": "First Normal Form",
                "paragraphs": [
                    "Each field should contain one atomic value."
                ],
                "bullets": [
                    {
                        "text": "Atomic values",
                        "children": [
                            "One value should be stored in each field."
                        ],
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
            "Normalization reduces unnecessary duplication."
        ],
    }

def test_valid_notes_pass_schema_validation() -> None:
    schema = NoteSchema()

    valid, errors = schema.validate(
        create_valid_notes()
    )

    assert valid is True
    assert errors == []

def test_normalize_cleans_and_removes_invalid_items() -> None:
    schema = NoteSchema()

    raw_notes = {
        "title": "  Lecture Topic  ",
        "sections": [
            {
                "heading": "  Main Section  ",
                "paragraphs": [
                    "  Useful paragraph.  ",
                    123,
                    "",
                ],
                "bullets": [
                    "  Simple bullet  ",
                    {
                        "text": "",
                        "children": [],
                    },
                ],
                "definitions": [
                    {
                        "term": "Term",
                        "definition": "Meaning",
                    },
                    {
                        "term": "",
                        "definition": "Missing term",
                    },
                ],
                "examples": "  One example.  ",
            }
        ],
    }

    normalized = schema.normalize(raw_notes)
    section = normalized["sections"][0]

    assert normalized["title"] == "Lecture Topic"
    assert normalized["subtitle"] == ""
    assert normalized["summary"] == []

    assert section["heading"] == "Main Section"
    assert section["paragraphs"] == [
        "Useful paragraph."
    ]

    assert section["bullets"] == [
        {
            "text": "Simple bullet",
            "children": [],
        }
    ]

    assert section["definitions"] == [
        {
            "term": "Term",
            "definition": "Meaning",
        }
    ]

    assert section["examples"] == [
        "One example."
    ]