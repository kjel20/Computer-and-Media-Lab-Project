import logging
from pathlib import Path
from typing import Any
import pymupdf
from config import (
    IGNORE_EMPTY_STYLE_SPANS,
    INDENT_TOLERANCE,
    NOTES_DIR,
    STYLE_FONT_SIZE_DECIMALS,
    STYLE_POSITION_DECIMALS,
    STYLE_SPACING_DECIMALS,
)

logger = logging.getLogger(__name__)

class StyleExtractor:
    """
    Extracts visual formatting information from
    text-based PDF note files.

    The extractor records:
    - text spans;
    - font names;
    - font sizes;
    - colors;
    - bounding boxes;
    - page positions;
    - approximate indentation;
    - approximate line and paragraph spacing.
    """

    def __init__(self, notes_dir: Path = NOTES_DIR,) -> None:
        """
        Create a style extractor.

        Parameters
        ----------
        notes_dir:
            Default directory containing reference PDFs.
        """

        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_pdf_files(self) -> list[Path]:
        """
        Return all PDF files in the notes directory.
        """

        if not self.notes_dir.exists():
            return []

        pdf_files = [
            path
            for path in self.notes_dir.iterdir()
            if (
                path.is_file()
                and path.suffix.lower() == ".pdf"
            )
        ]

        pdf_files.sort(
            key=lambda path: path.name.lower()
        )
        return pdf_files

    def extract_all_pdfs(self,) -> list[dict[str, Any]]:
        """
        Extract style data from every PDF in the
        reference-notes directory.

        Files that cannot be read are skipped.
        """

        pdf_files = self.get_pdf_files()

        if not pdf_files:
            logger.warning(
                "No PDF reference notes were found in %s.",
                self.notes_dir,
            )
            return []

        documents = []

        for pdf_path in pdf_files:
            try:
                document_data = (
                    self.extract_pdf(pdf_path)
                )
            except Exception:
                logger.exception(
                    "Could not extract style from %s.",
                    pdf_path.name,
                )
                continue

            documents.append(
                document_data
            )

        logger.info(
            "Extracted style data from %d PDF file(s).",
            len(documents),
        )
        return documents

    def extract_pdf(self, pdf_path: Path,) -> dict[str, Any]:
        """
        Extract all available formatting data from
        one PDF file.
        """

        pdf_path = Path(pdf_path)

        self._validate_pdf_path(
            pdf_path
        )

        try:
            document = pymupdf.open(
                pdf_path
            )

        except Exception as error:
            raise ValueError(
                f"Could not open PDF: {pdf_path.name}"
            ) from error

        pages = []
        all_spans = []
        all_lines = []

        try:
            if document.needs_pass:
                raise ValueError(
                    f"PDF is password-protected: "
                    f"{pdf_path.name}"
                )

            for page_index, page in enumerate(
                document
            ):
                page_data = self._extract_page(
                    page=page,
                    page_number=page_index + 1,
                )

                pages.append(page_data)

                all_spans.extend(
                    page_data["spans"]
                )

                all_lines.extend(
                    page_data["lines"]
                )

        finally:
            document.close()

        return {
            "source": pdf_path.name,
            "path": pdf_path,
            "page_count": len(pages),
            "pages": pages,
            "spans": all_spans,
            "lines": all_lines,
            "span_count": len(all_spans),
            "line_count": len(all_lines),
        }

    def _validate_pdf_path(self, pdf_path: Path,) -> None:
        """
        Ensure the supplied path points to a PDF.
        """

        if not pdf_path.exists():
            raise FileNotFoundError(
                f"PDF does not exist: {pdf_path}"
            )

        if not pdf_path.is_file():
            raise ValueError(
                f"PDF path is not a file: {pdf_path}"
            )

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(
                "StyleExtractor only accepts PDF files."
            )

    def _extract_page(self, page: pymupdf.Page, page_number: int,) -> dict[str, Any]:
        """
        Extract blocks, lines, spans, and page-level
        measurements from one PDF page.
        """

        page_rect = page.rect

        page_width = round(
            float(page_rect.width),
            STYLE_POSITION_DECIMALS,
        )

        page_height = round(
            float(page_rect.height),
            STYLE_POSITION_DECIMALS,
        )

        page_dictionary = page.get_text(
            "dict",
            sort=True,
        )

        raw_lines = self._collect_raw_lines(
            page_dictionary=page_dictionary,
            page_number=page_number,
            page_width=page_width,
            page_height=page_height,
        )

        # The smallest line x-coordinate is treated as the approximate normal left text margin.
        page_text_left = self._find_page_text_left(
            raw_lines
        )

        completed_lines = (
            self._calculate_line_spacing_and_indents(
                lines=raw_lines,
                page_text_left=page_text_left,
            )
        )

        page_spans = []

        for line in completed_lines:
            page_spans.extend(
                line["spans"]
            )

        return {
            "page_number": page_number,
            "width": page_width,
            "height": page_height,
            "page_text_left": page_text_left,
            "line_count": len(completed_lines),
            "span_count": len(page_spans),
            "lines": completed_lines,
            "spans": page_spans,
        }

    def _collect_raw_lines(
        self,
        page_dictionary: dict[str, Any],
        page_number: int,
        page_width: float,
        page_height: float,
    ) -> list[dict[str, Any]]:
        """
        Convert PyMuPDF's nested blocks, lines, and
        spans into a simple list of line dictionaries.
        """

        lines = []
        line_number = 0

        for block_index, block in enumerate(
            page_dictionary.get(
                "blocks",
                [],
            )
        ):
            # Block type 0 represents text.
            if block.get("type") != 0:
                continue

            for block_line_index, line in enumerate(
                block.get(
                    "lines",
                    [],
                )
            ):
                extracted_spans = []

                for span_index, span in enumerate(
                    line.get(
                        "spans",
                        [],
                    )
                ):
                    extracted_span = self._extract_span(
                        span=span,
                        page_number=page_number,
                        block_index=block_index,
                        line_number=line_number,
                        span_index=span_index,
                        page_width=page_width,
                        page_height=page_height,
                    )

                    if extracted_span is not None:
                        extracted_spans.append(
                            extracted_span
                        )

                if not extracted_spans:
                    continue

                line_text = "".join(
                    span["text"]
                    for span in extracted_spans
                ).strip()

                if not line_text:
                    continue

                bbox = line.get(
                    "bbox",
                    self._combine_bboxes(
                        [
                            span["bbox"]
                            for span
                            in extracted_spans
                        ]
                    ),
                )

                line_bbox = self._round_bbox(
                    bbox
                )

                direction = line.get(
                    "dir",
                    (1.0, 0.0),
                )

                lines.append(
                    {
                        "page_number": page_number,
                        "block_index": block_index,
                        "block_line_index": (
                            block_line_index
                        ),
                        "line_number": line_number,
                        "text": line_text,
                        "bbox": line_bbox,
                        "x0": line_bbox[0],
                        "y0": line_bbox[1],
                        "x1": line_bbox[2],
                        "y1": line_bbox[3],
                        "width": round(
                            line_bbox[2]
                            - line_bbox[0],
                            STYLE_POSITION_DECIMALS,
                        ),
                        "height": round(
                            line_bbox[3]
                            - line_bbox[1],
                            STYLE_POSITION_DECIMALS,
                        ),
                        "direction": (
                            round(
                                float(direction[0]),
                                STYLE_POSITION_DECIMALS,
                            ),
                            round(
                                float(direction[1]),
                                STYLE_POSITION_DECIMALS,
                            ),
                        ),
                        "spans": extracted_spans,
                    }
                )

                line_number += 1

        lines.sort(
            key=lambda line: (
                line["y0"],
                line["x0"],
            )
        )

        # Reassign numbers after spatial sorting.
        for index, line in enumerate(lines):
            line["line_number"] = index

            for span in line["spans"]:
                span["line_number"] = index
        return lines

    def _extract_span(
        self,
        span: dict[str, Any],
        page_number: int,
        block_index: int,
        line_number: int,
        span_index: int,
        page_width: float,
        page_height: float,
    ) -> dict[str, Any] | None:
        """
        Convert one PyMuPDF span into normalized
        formatting information.
        """

        text = span.get(
            "text",
            "",
        )

        if not isinstance(text, str):
            text = str(text)

        if (
            IGNORE_EMPTY_STYLE_SPANS
            and not text.strip()
        ):
            return None

        bbox = self._round_bbox(
            span.get(
                "bbox",
                (0.0, 0.0, 0.0, 0.0),
            )
        )

        font_name = str(
            span.get(
                "font",
                "Unknown",
            )
        )

        font_size = round(
            float(
                span.get(
                    "size",
                    0.0,
                )
            ),
            STYLE_FONT_SIZE_DECIMALS,
        )

        color_integer = int(
            span.get(
                "color",
                0,
            )
        )

        flags = int(
            span.get(
                "flags",
                0,
            )
        )

        ascender = span.get("ascender")
        descender = span.get("descender")

        return {
            "text": text,
            "page_number": page_number,
            "block_index": block_index,
            "line_number": line_number,
            "span_index": span_index,
            "font": font_name,
            "font_size": font_size,
            "color": color_integer,
            "color_hex": self._color_to_hex(
                color_integer
            ),
            "flags": flags,
            "is_bold": self._is_bold(
                font_name,
                flags,
            ),
            "is_italic": self._is_italic(
                font_name,
                flags,
            ),
            "bbox": bbox,
            "x0": bbox[0],
            "y0": bbox[1],
            "x1": bbox[2],
            "y1": bbox[3],
            "width": round(
                bbox[2] - bbox[0],
                STYLE_POSITION_DECIMALS,
            ),
            "height": round(
                bbox[3] - bbox[1],
                STYLE_POSITION_DECIMALS,
            ),
            "distance_from_page_left": round(
                bbox[0],
                STYLE_POSITION_DECIMALS,
            ),
            "distance_from_page_top": round(
                bbox[1],
                STYLE_POSITION_DECIMALS,
            ),
            "distance_from_page_right": round(
                max(
                    page_width - bbox[2],
                    0.0,
                ),
                STYLE_POSITION_DECIMALS,
            ),
            "distance_from_page_bottom": round(
                max(
                    page_height - bbox[3],
                    0.0,
                ),
                STYLE_POSITION_DECIMALS,
            ),
            "ascender": (
                round(
                    float(ascender),
                    STYLE_POSITION_DECIMALS,
                )
                if ascender is not None
                else None
            ),
            "descender": (
                round(
                    float(descender),
                    STYLE_POSITION_DECIMALS,
                )
                if descender is not None
                else None
            ),
        }

    def _find_page_text_left(self, lines: list[dict[str, Any]],) -> float:
        """
        Estimate the page's normal left text position.

        The minimum line x-position is used for this
        initial extraction stage.
        """

        if not lines:
            return 0.0

        return round(
            min(
                line["x0"]
                for line in lines
            ),
            STYLE_POSITION_DECIMALS,
        )

    def _calculate_line_spacing_and_indents(self, lines: list[dict[str, Any]], page_text_left: float,) -> list[dict[str, Any]]:
        """
        Add indentation and spacing estimates.

        Paragraph spacing is approximated as the
        vertical gap between the previous line's
        bottom and the current line's top.
        """

        previous_line = None

        for line in lines:
            absolute_indent = line["x0"]

            relative_indent = max(
                line["x0"] - page_text_left,
                0.0,
            )

            line["absolute_indent"] = round(
                absolute_indent,
                STYLE_POSITION_DECIMALS,
            )

            line["relative_indent"] = round(
                relative_indent,
                STYLE_POSITION_DECIMALS,
            )

            line["is_indented"] = (
                relative_indent
                > INDENT_TOLERANCE
            )

            if previous_line is None:
                spacing_before = line["y0"]

            else:
                spacing_before = max(
                    line["y0"]
                    - previous_line["y1"],
                    0.0,
                )

            line["spacing_before"] = round(
                spacing_before,
                STYLE_SPACING_DECIMALS,
            )

            if previous_line is None:
                line["baseline_distance"] = None

            else:
                line["baseline_distance"] = round(
                    max(
                        line["y0"]
                        - previous_line["y0"],
                        0.0,
                    ),
                    STYLE_SPACING_DECIMALS,
                )

            for span in line["spans"]:
                span["page_text_left"] = (
                    page_text_left
                )

                span["relative_indent"] = round(
                    max(
                        span["x0"]
                        - page_text_left,
                        0.0,
                    ),
                    STYLE_POSITION_DECIMALS,
                )

                span["line_spacing_before"] = (
                    line["spacing_before"]
                )

            previous_line = line

        # Add spacing after by looking at the next line.
        for index, line in enumerate(lines):
            if index == len(lines) - 1:
                spacing_after = 0.0

            else:
                next_line = lines[index + 1]

                spacing_after = max(
                    next_line["y0"]
                    - line["y1"],
                    0.0,
                )

            line["spacing_after"] = round(
                spacing_after,
                STYLE_SPACING_DECIMALS,
            )

        return lines

    def _round_bbox(self, bbox: Any,) -> tuple[float, float, float, float]:
        """
        Convert a bounding box into a rounded tuple.
        """

        if (
            not isinstance(
                bbox,
                (list, tuple),
            )
            or len(bbox) != 4
        ):
            bbox = (
                0.0,
                0.0,
                0.0,
                0.0,
            )

        return tuple(
            round(
                float(value),
                STYLE_POSITION_DECIMALS,
            )
            for value in bbox
        )

    def _combine_bboxes(
        self,
        bboxes: list[
            tuple[float, float, float, float]
        ],
    ) -> tuple[float, float, float, float]:
        """
        Create one bounding box surrounding all
        supplied bounding boxes.
        """

        if not bboxes:
            return (
                0.0,
                0.0,
                0.0,
                0.0,
            )

        return (
            min(bbox[0] for bbox in bboxes),
            min(bbox[1] for bbox in bboxes),
            max(bbox[2] for bbox in bboxes),
            max(bbox[3] for bbox in bboxes),
        )

    def _color_to_hex(self, color: int,) -> str:
        """
        Convert PyMuPDF's integer RGB value into
        a normal hexadecimal color string.
        """

        color = max(
            0,
            min(
                int(color),
                0xFFFFFF,
            ),
        )

        return f"#{color:06X}"

    def _is_bold(
        self,
        font_name: str,
        flags: int,
    ) -> bool:
        """
        Estimate whether a span uses a bold font.

        Font naming is checked first. The flags value
        is retained in the output for later refinement.
        """

        normalized_name = (
            font_name.lower()
        )

        bold_terms = (
            "bold",
            "black",
            "heavy",
            "semibold",
            "demibold",
        )

        if any(
            term in normalized_name
            for term in bold_terms
        ):
            return True

        # PyMuPDF font flags commonly use bit 4 for bold text.
        return bool(flags & 16)

    def _is_italic(self, font_name: str, flags: int,) -> bool:
        """
        Estimate whether a span uses italic or
        oblique formatting.
        """

        normalized_name = (
            font_name.lower()
        )

        italic_terms = (
            "italic",
            "oblique",
            "slanted",
        )

        if any(
            term in normalized_name
            for term in italic_terms
        ):
            return True

        # PyMuPDF font flags commonly use bit 1 for italic text.
        return bool(flags & 2)