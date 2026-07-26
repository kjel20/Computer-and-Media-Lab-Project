import json
import logging
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any
from config import (
    DEFAULT_BODY_FONT,
    DEFAULT_BODY_FONT_SIZE,
    DEFAULT_FALLBACK_FONT,
    DEFAULT_HEADING_1_SIZE,
    DEFAULT_HEADING_2_SIZE,
    DEFAULT_HEADING_3_SIZE,
    DEFAULT_TITLE_SIZE,
    INDENT_TOLERANCE,
    MAX_NORMAL_PARAGRAPH_GAP,
    STYLE_PROFILE_FILENAME,
    STYLE_PROFILES_DIR,
)

logger = logging.getLogger(__name__)

class StyleProfileBuilder:
    """Summarizes raw StyleExtractor data into one reusable style profile."""

    def __init__(self, output_dir: Path = STYLE_PROFILES_DIR) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_profile(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        valid_documents = self._validate_documents(documents)

        if not valid_documents:
            logger.warning("No valid style documents were provided. Using defaults.")
            return self._create_default_profile()

        spans = self._collect_spans(valid_documents)
        lines = self._collect_lines(valid_documents)
        pages = self._collect_pages(valid_documents)
        source_files = sorted({
            document.get("source", "unknown")
            for document in valid_documents
        })

        if not spans:
            logger.warning("No usable spans were found. Using default text styles.")
            return self._create_default_profile(source_files)

        body_style = self._infer_body_style(spans)
        title_style, title_identity = self._infer_title_style(lines, body_style)
        headings = self._infer_heading_styles(lines, body_style, title_identity)
        spacing = self._infer_spacing(lines, body_style)

        profile = {
            "profile_version": 1,
            "source_files": source_files,
            "source_file_count": len(source_files),
            "page": self._infer_page_style(pages),
            "body": {
                **body_style,
                "line_spacing_points": spacing["line_spacing_points"],
                "line_spacing_ratio": spacing["line_spacing_ratio"],
                "paragraph_spacing_before": spacing["paragraph_spacing_before"],
                "paragraph_spacing_after": spacing["paragraph_spacing_after"],
            },
            "title": title_style,
            "heading_1": headings["heading_1"],
            "heading_2": headings["heading_2"],
            "heading_3": headings["heading_3"],
            "bullet": self._infer_bullet_style(lines, body_style),
            "common_colors": self._infer_common_colors(spans),
            "analysis": {
                "documents_processed": len(valid_documents),
                "pages_processed": len(pages),
                "lines_processed": len(lines),
                "spans_processed": len(spans),
            },
        }

        logger.info(
            "Built style profile from %d documents, %d pages, %d lines, and %d spans.",
            len(valid_documents), len(pages), len(lines), len(spans)
        )
        return profile

    def save_profile(self, profile: dict[str, Any], filename: str = STYLE_PROFILE_FILENAME) -> Path:
        if not isinstance(profile, dict):
            raise TypeError("Style profile must be a dictionary.")

        filename = filename.strip()
        if not filename:
            raise ValueError("Profile filename cannot be empty.")
        if not filename.lower().endswith(".json"):
            filename += ".json"

        output_path = self.output_dir / filename

        try:
            output_path.write_text(
                json.dumps(profile, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            logger.exception("Could not save style profile to %s.", output_path)
            raise RuntimeError("The style profile could not be saved.") from error

        logger.info("Style profile saved to %s.", output_path)
        return output_path

    def build_and_save(self, documents: list[dict[str, Any]], filename: str = STYLE_PROFILE_FILENAME) -> tuple[dict[str, Any], Path]:
        profile = self.build_profile(documents)
        return profile, self.save_profile(profile, filename)

    def load_profile(self, profile_path: Path | None = None) -> dict[str, Any]:
        profile_path = Path(
            profile_path or self.output_dir / STYLE_PROFILE_FILENAME
        )

        if not profile_path.exists():
            raise FileNotFoundError(f"Style profile does not exist: {profile_path}")
        if not profile_path.is_file():
            raise ValueError(f"Style profile path is not a file: {profile_path}")

        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("The style-profile file does not contain valid JSON.") from error
        except OSError as error:
            raise RuntimeError("The style-profile file could not be read.") from error

        if not isinstance(profile, dict):
            raise ValueError("The loaded style profile must be a JSON object.")

        return profile

    def normalize_font_name(self, font_name: str) -> str:
        """Remove PDF subset prefixes and common style suffixes."""

        if not isinstance(font_name, str) or not font_name.strip():
            return DEFAULT_FALLBACK_FONT

        font_name = re.sub(r"^[A-Z]{6}\+", "", font_name.strip())

        replacements = {
            "TimesNewRomanPSMT": "Times New Roman",
            "TimesNewRomanPS-BoldMT": "Times New Roman",
            "TimesNewRomanPS-ItalicMT": "Times New Roman",
            "ArialMT": "Arial",
            "Arial-BoldMT": "Arial",
            "Arial-ItalicMT": "Arial",
            "Calibri-Light": "Calibri Light",
            "AptosDisplay": "Aptos Display",
            "Aptos-Display": "Aptos Display",
            "HelveticaNeue": "Helvetica Neue",
        }

        if font_name in replacements:
            return replacements[font_name]

        suffixes = [
            "-BoldItalic", "-BoldOblique", "-SemiBoldItalic",
            "-SemiboldItalic", "-SemiBold", "-Semibold",
            "-DemiBold", "-Demibold", "-BoldMT", "-ItalicMT",
            "-Oblique", "-Italic", "-Regular", "-Medium",
            "-Bold", ",Bold", ",Italic",
        ]

        for suffix in suffixes:
            if font_name.endswith(suffix):
                font_name = font_name[:-len(suffix)]
                break

        font_name = re.sub(r"\s+", " ", font_name.replace("_", " ")).strip()
        return font_name or DEFAULT_FALLBACK_FONT

    def _validate_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(documents, list):
            raise TypeError("Documents must be provided as a list.")

        valid = []

        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                logger.warning("Skipping document %d because it is not a dictionary.", index)
                continue
            if not isinstance(document.get("pages", []), list):
                logger.warning("Skipping document %d because its pages value is invalid.", index)
                continue
            valid.append(document)

        return valid

    def _collect_spans(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        spans = []

        for document in documents:
            source = document.get("source", "unknown")

            for span in document.get("spans", []):
                if not isinstance(span, dict):
                    continue

                text = span.get("text", "")
                if not isinstance(text, str) or not text.strip():
                    continue

                span_copy = span.copy()
                span_copy["source"] = source
                span_copy["normalized_font"] = self.normalize_font_name(
                    span.get("font", DEFAULT_BODY_FONT)
                )
                spans.append(span_copy)

        return spans

    def _collect_lines(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lines = []

        for document in documents:
            source = document.get("source", "unknown")

            for page in document.get("pages", []):
                page_number = page.get("page_number", 0)
                page_height = self._safe_float(page.get("height", 0), 0)

                for line in page.get("lines", []):
                    if not isinstance(line, dict):
                        continue

                    text = line.get("text", "")
                    if not isinstance(text, str) or not text.strip():
                        continue

                    line_copy = line.copy()
                    line_copy["source"] = source
                    line_copy["page_number"] = page_number
                    line_copy["page_height"] = page_height
                    line_copy["spans"] = []

                    for span in line.get("spans", []):
                        if not isinstance(span, dict):
                            continue

                        span_copy = span.copy()
                        span_copy["normalized_font"] = self.normalize_font_name(
                            span.get("font", DEFAULT_BODY_FONT)
                        )
                        line_copy["spans"].append(span_copy)

                    lines.append(line_copy)

        return lines

    def _collect_pages(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pages = []

        for document in documents:
            source = document.get("source", "unknown")

            for page in document.get("pages", []):
                if isinstance(page, dict):
                    page_copy = page.copy()
                    page_copy["source"] = source
                    pages.append(page_copy)

        return pages

    def _infer_body_style(self, spans: list[dict[str, Any]]) -> dict[str, Any]:
        style_weights = Counter()

        for span in spans:
            text = span.get("text", "").strip()
            size = self._safe_float(
                span.get("font_size", DEFAULT_BODY_FONT_SIZE),
                DEFAULT_BODY_FONT_SIZE,
            )

            if not text or size < 5 or size > 30:
                continue

            style = (
                span.get("normalized_font", DEFAULT_BODY_FONT),
                round(size, 1),
                bool(span.get("is_bold", False)),
                bool(span.get("is_italic", False)),
                span.get("color_hex", "#000000"),
            )
            style_weights[style] += len(text)

        if not style_weights:
            return self._default_text_style(DEFAULT_BODY_FONT_SIZE, bold=False)

        font, size, bold, italic, color = style_weights.most_common(1)[0][0]

        return {
            "font": font,
            "font_size": size,
            "bold": bold,
            "italic": italic,
            "color": color,
        }

    def _infer_title_style(self, lines: list[dict[str, Any]], body_style: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, int, int] | None]:
        body_size = float(body_style["font_size"])
        candidates = []

        for line in lines:
            text = line.get("text", "").strip()
            page_number = int(line.get("page_number", 0))
            page_height = self._safe_float(line.get("page_height", 0), 0)
            y0 = self._safe_float(line.get("y0", 0), 0)

            if not text or len(text) > 180 or page_number != 1:
                continue
            if page_height > 0 and y0 > page_height * 0.40:
                continue

            style = self._get_line_style(line)
            if style["font_size"] < body_size + 2:
                continue

            top_bonus = (1 - min(y0 / page_height, 1)) * 5 if page_height > 0 else 0
            score = (
                style["font_size"] * 3
                + top_bonus
                + (5 if style["bold"] else 0)
                - min(len(text) / 50, 4)
            )
            candidates.append((score, line, style))

        if not candidates:
            return {
                "font": body_style["font"],
                "font_size": max(DEFAULT_TITLE_SIZE, body_size + 6),
                "bold": True,
                "italic": False,
                "color": body_style["color"],
                "alignment": "left",
                "spacing_after": 12.0,
            }, None

        _, title_line, title_style = max(candidates, key=lambda item: item[0])

        identity = (
            title_line.get("source", "unknown"),
            int(title_line.get("page_number", 0)),
            int(title_line.get("line_number", 0)),
        )

        return {
            **title_style,
            "alignment": "left",
            "spacing_after": 12.0,
        }, identity

    def _infer_heading_styles(self, lines: list[dict[str, Any]], body_style: dict[str, Any], title_identity: tuple[str, int, int] | None) -> dict[str, dict[str, Any]]:
        body_size = float(body_style["font_size"])
        style_weights = Counter()

        for line in lines:
            identity = (
                line.get("source", "unknown"),
                int(line.get("page_number", 0)),
                int(line.get("line_number", 0)),
            )

            if title_identity is not None and identity == title_identity:
                continue

            text = line.get("text", "").strip()
            if not text or len(text) > 140:
                continue

            style = self._get_line_style(line)

            if not (
                style["font_size"] >= body_size + 1
                or (style["bold"] and len(text) <= 100)
            ):
                continue

            key = (
                style["font"],
                round(style["font_size"], 1),
                style["bold"],
                style["italic"],
                style["color"],
            )
            style_weights[key] += max(len(text), 1)

        sorted_styles = sorted(
            style_weights.items(),
            key=lambda item: (item[0][1], item[1]),
            reverse=True,
        )

        detected = []
        used_sizes = set()

        for style_key, _ in sorted_styles:
            font, size, bold, italic, color = style_key
            size = round(float(size), 1)

            if size in used_sizes:
                continue

            used_sizes.add(size)
            detected.append({
                "font": font,
                "font_size": size,
                "bold": bold,
                "italic": italic,
                "color": color,
            })

            if len(detected) == 3:
                break

        defaults = [
            self._heading_default(body_style, max(DEFAULT_HEADING_1_SIZE, body_size + 4)),
            self._heading_default(body_style, max(DEFAULT_HEADING_2_SIZE, body_size + 2)),
            self._heading_default(body_style, max(DEFAULT_HEADING_3_SIZE, body_size + 1)),
        ]

        while len(detected) < 3:
            detected.append(defaults[len(detected)])

        return {
            "heading_1": {**detected[0], "spacing_before": 12.0, "spacing_after": 6.0},
            "heading_2": {**detected[1], "spacing_before": 10.0, "spacing_after": 5.0},
            "heading_3": {**detected[2], "spacing_before": 8.0, "spacing_after": 4.0},
        }

    def _infer_page_style(self, pages: list[dict[str, Any]]) -> dict[str, Any]:
        if not pages:
            return self._default_page_style()

        widths, heights = [], []
        lefts, rights, tops, bottoms = [], [], [], []

        for page in pages:
            width = self._safe_float(page.get("width", 0), 0)
            height = self._safe_float(page.get("height", 0), 0)
            lines = [
                line for line in page.get("lines", [])
                if isinstance(line, dict) and str(line.get("text", "")).strip()
            ]

            if width > 0:
                widths.append(width)
            if height > 0:
                heights.append(height)
            if not lines:
                continue

            min_x = min(self._safe_float(line.get("x0", 0), 0) for line in lines)
            max_x = max(self._safe_float(line.get("x1", 0), 0) for line in lines)
            min_y = min(self._safe_float(line.get("y0", 0), 0) for line in lines)
            max_y = max(self._safe_float(line.get("y1", 0), 0) for line in lines)

            lefts.append(max(min_x, 0))
            tops.append(max(min_y, 0))

            if width > 0:
                rights.append(max(width - max_x, 0))
            if height > 0:
                bottoms.append(max(height - max_y, 0))

        return {
            "width": self._median_or_default(widths, 595.3),
            "height": self._median_or_default(heights, 841.9),
            "margin_left": self._median_or_default(lefts, 72.0),
            "margin_right": self._median_or_default(rights, 72.0),
            "margin_top": self._median_or_default(tops, 72.0),
            "margin_bottom": self._median_or_default(bottoms, 72.0),
        }

    def _infer_spacing(self, lines: list[dict[str, Any]], body_style: dict[str, Any]) -> dict[str, float]:
        body_size = float(body_style["font_size"])
        baseline_distances = []
        visible_gaps = []

        for line in lines:
            style = self._get_line_style(line)

            if abs(style["font_size"] - body_size) > 1:
                continue

            baseline = line.get("baseline_distance")
            if baseline is not None:
                baseline = self._safe_float(baseline, 0)

                if 0 < baseline <= body_size * 2.5:
                    baseline_distances.append(baseline)

            gap = self._safe_float(line.get("spacing_before", 0), 0)
            if 0 < gap <= MAX_NORMAL_PARAGRAPH_GAP:
                visible_gaps.append(gap)

        line_points = self._median_or_default(
            baseline_distances,
            body_size * 1.15,
        )
        ratio = round(max(line_points / max(body_size, 1), 1), 2)

        if visible_gaps:
            normal_gap = median(visible_gaps)
            paragraph_gaps = [
                gap for gap in visible_gaps
                if gap > max(normal_gap * 1.5, normal_gap + 2)
            ]
            paragraph_spacing = self._median_or_default(
                paragraph_gaps,
                normal_gap,
            )
        else:
            paragraph_spacing = 6.0

        return {
            "line_spacing_points": round(line_points, 1),
            "line_spacing_ratio": ratio,
            "paragraph_spacing_before": 0.0,
            "paragraph_spacing_after": round(paragraph_spacing, 1),
        }

    def _infer_bullet_style(self, lines: list[dict[str, Any]], body_style: dict[str, Any]) -> dict[str, Any]:
        bullet_pattern = re.compile(
            r"^\s*([•◦▪●○■□‣]|[-*]|\d+[.)]|[A-Za-z][.)])\s+"
        )

        explicit, fallback = [], []

        for line in lines:
            text = line.get("text", "")
            indent = self._safe_float(line.get("relative_indent", 0), 0)

            if not isinstance(text, str) or indent <= INDENT_TOLERANCE:
                continue

            fallback.append(indent)

            if bullet_pattern.match(text):
                explicit.append(indent)

        body_size = float(body_style["font_size"])
        bullet_indent = self._infer_common_indent(
            explicit or fallback,
            default=max(body_size * 2, 18.0),
        )
        hanging_indent = round(max(body_size, bullet_indent * 0.35), 1)

        return {
            "font": body_style["font"],
            "font_size": body_style["font_size"],
            "color": body_style["color"],
            "indent_left": bullet_indent,
            "hanging_indent": hanging_indent,
            "nested_indent_increment": bullet_indent,
            "spacing_after": 3.0,
        }

    def _infer_common_colors(self, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        color_weights = Counter()

        for span in spans:
            text = str(span.get("text", "")).strip()

            if text:
                color_weights[span.get("color_hex", "#000000")] += len(text)

        total = sum(color_weights.values())

        if not total:
            return [{"color": "#000000", "text_weight": 0, "percentage": 100.0}]

        return [
            {
                "color": color,
                "text_weight": weight,
                "percentage": round(weight / total * 100, 2),
            }
            for color, weight in color_weights.most_common(5)
        ]

    def _get_line_style(self, line: dict[str, Any]) -> dict[str, Any]:
        style_weights = Counter()

        for span in line.get("spans", []):
            if not isinstance(span, dict):
                continue

            text = str(span.get("text", "")).strip()
            if not text:
                continue

            key = (
                span.get(
                    "normalized_font",
                    self.normalize_font_name(span.get("font", DEFAULT_BODY_FONT)),
                ),
                round(
                    self._safe_float(
                        span.get("font_size", DEFAULT_BODY_FONT_SIZE),
                        DEFAULT_BODY_FONT_SIZE,
                    ),
                    1,
                ),
                bool(span.get("is_bold", False)),
                bool(span.get("is_italic", False)),
                span.get("color_hex", "#000000"),
            )
            style_weights[key] += len(text)

        if not style_weights:
            return self._default_text_style(DEFAULT_BODY_FONT_SIZE, bold=False)

        font, size, bold, italic, color = style_weights.most_common(1)[0][0]

        return {
            "font": font,
            "font_size": size,
            "bold": bold,
            "italic": italic,
            "color": color,
        }

    def _infer_common_indent(self, indents: list[float], default: float) -> float:
        if not indents:
            return round(default, 1)

        grouping_size = max(INDENT_TOLERANCE, 1.0)
        grouped = Counter(
            round(round(indent / grouping_size) * grouping_size, 1)
            for indent in indents
        )

        return float(grouped.most_common(1)[0][0])

    def _create_default_profile(self, source_files: list[str] | None = None) -> dict[str, Any]:
        source_files = source_files or []

        body = {
            **self._default_text_style(DEFAULT_BODY_FONT_SIZE, bold=False),
            "line_spacing_points": round(DEFAULT_BODY_FONT_SIZE * 1.15, 1),
            "line_spacing_ratio": 1.15,
            "paragraph_spacing_before": 0.0,
            "paragraph_spacing_after": 6.0,
        }

        return {
            "profile_version": 1,
            "source_files": source_files,
            "source_file_count": len(source_files),
            "page": self._default_page_style(),
            "body": body,
            "title": {
                **self._default_text_style(DEFAULT_TITLE_SIZE),
                "alignment": "left",
                "spacing_after": 12.0,
            },
            "heading_1": {
                **self._default_text_style(DEFAULT_HEADING_1_SIZE),
                "spacing_before": 12.0,
                "spacing_after": 6.0,
            },
            "heading_2": {
                **self._default_text_style(DEFAULT_HEADING_2_SIZE),
                "spacing_before": 10.0,
                "spacing_after": 5.0,
            },
            "heading_3": {
                **self._default_text_style(DEFAULT_HEADING_3_SIZE),
                "spacing_before": 8.0,
                "spacing_after": 4.0,
            },
            "bullet": {
                "font": DEFAULT_BODY_FONT,
                "font_size": DEFAULT_BODY_FONT_SIZE,
                "color": "#000000",
                "indent_left": 24.0,
                "hanging_indent": 12.0,
                "nested_indent_increment": 24.0,
                "spacing_after": 3.0,
            },
            "common_colors": [
                {"color": "#000000", "text_weight": 0, "percentage": 100.0}
            ],
            "analysis": {
                "documents_processed": 0,
                "pages_processed": 0,
                "lines_processed": 0,
                "spans_processed": 0,
            },
        }

    def _default_text_style(self, size: float, bold: bool = True) -> dict[str, Any]:
        return {
            "font": DEFAULT_BODY_FONT,
            "font_size": size,
            "bold": bold,
            "italic": False,
            "color": "#000000",
        }

    def _heading_default(self, body_style: dict[str, Any], size: float) -> dict[str, Any]:
        return {
            "font": body_style["font"],
            "font_size": size,
            "bold": True,
            "italic": False,
            "color": body_style["color"],
        }

    def _default_page_style(self) -> dict[str, float]:
        return {
            "width": 595.3,
            "height": 841.9,
            "margin_left": 72.0,
            "margin_right": 72.0,
            "margin_top": 72.0,
            "margin_bottom": 72.0,
        }

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _median_or_default(self, values: list[float], default: float) -> float:
        usable = [float(value) for value in values if value is not None]
        return round(float(median(usable)), 1) if usable else round(float(default), 1)