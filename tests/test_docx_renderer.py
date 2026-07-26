from pathlib import Path
from docx import Document
from src.docx_renderer import DocxRenderer

def create_style_profile() -> dict:
    return {
        "page": {
            "width": 596.0,
            "height": 842.0,
            "margin_left": 72.0,
            "margin_right": 72.0,
            "margin_top": 72.0,
            "margin_bottom": 72.0,
        },
        "body": {
            "font": "Arial",
            "font_size": 11.0,
            "bold": False,
            "italic": False,
            "color": "#000000",
            "line_spacing_points": 14.0,
            "line_spacing_ratio": 1.2,
            "paragraph_spacing_before": 0.0,
            "paragraph_spacing_after": 5.0,
        },
        "title": {
            "font": "Arial",
            "font_size": 18.0,
            "bold": True,
            "italic": False,
            "color": "#000000",
            "alignment": "left",
            "spacing_after": 12.0,
        },
        "heading_1": {
            "font": "Arial",
            "font_size": 16.0,
            "bold": True,
            "italic": False,
            "color": "#000000",
            "spacing_before": 12.0,
            "spacing_after": 6.0,
        },
        "heading_2": {
            "font": "Arial",
            "font_size": 13.0,
            "bold": True,
            "italic": False,
            "color": "#000000",
            "spacing_before": 10.0,
            "spacing_after": 5.0,
        },
        "heading_3": {
            "font": "Arial",
            "font_size": 11.0,
            "bold": True,
            "italic": False,
            "color": "#000000",
            "spacing_before": 8.0,
            "spacing_after": 4.0,
        },
        "bullet": {
            "font": "Arial",
            "font_size": 11.0,
            "color": "#000000",
            "indent_left": 18.0,
            "hanging_indent": 10.0,
            "nested_indent_increment": 18.0,
            "spacing_after": 2.0,
        },
    }

def create_structured_notes() -> dict:
    return {
        "title": "Database Normalization",
        "subtitle": "",
        "sections": [
            {
                "heading": "First Normal Form",
                "paragraphs": [
                    (
                        "First normal form requires "
                        "atomic values."
                    )
                ],
                "bullets": [
                    {
                        "text": (
                            "Each field stores one value."
                        ),
                        "children": [
                            (
                                "Multiple values should "
                                "be separated."
                            )
                        ],
                    }
                ],
                "definitions": [
                    {
                        "term": "Atomic value",
                        "definition": (
                            "is one indivisible piece "
                            "of data."
                        ),
                    }
                ],
                "examples": [],
            }
        ],
        "summary": [
            (
                "Normalization reduces unnecessary "
                "duplication."
            )
        ],
    }

def test_renderer_creates_readable_docx(
    tmp_path: Path,
) -> None:
    renderer = DocxRenderer(
        output_dir=tmp_path
    )

    output_path = renderer.render(
        notes=create_structured_notes(),
        style_profile=create_style_profile(),
        filename="test_notes",
    )

    assert output_path.exists()
    assert output_path.suffix == ".docx"
    assert output_path.stat().st_size > 0

    document = Document(output_path)

    full_text = "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
    )

    assert "Database Normalization" in full_text
    assert "FIRST NORMAL FORM" in full_text.upper()
    assert "Atomic value" in full_text
    assert (
        "Normalization reduces unnecessary duplication."
        in full_text
    )