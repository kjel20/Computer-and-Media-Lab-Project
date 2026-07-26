import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

class ContentQualityValidator:
    """Checks whether structured lecture notes contain useful content."""

    PLACEHOLDER_VALUES = {
        "example",
        "example title",
        "example subtitle",
        "lecture title",
        "lecture notes",
        "section",
        "section heading",
        "example section",
        "paragraph",
        "example paragraph",
        "explanatory paragraph",
        "explanatory paragraph based on the transcript",
        "paragraph based on the transcript",
        "main bullet",
        "main bullet point",
        "bullet",
        "bullet point",
        "bullet 1",
        "bullet 2",
        "nested bullet",
        "supporting point",
        "nested supporting point",
        "term",
        "term 1",
        "term 2",
        "technical term",
        "definition",
        "definition 1",
        "definition 2",
        "definition supported by the transcript",
        "example definition",
        "summary",
        "final takeaway",
        "important takeaway",
        "important final takeaway",
        "example supported by the transcript",
        "example stated or clearly supported by the transcript",
        "transcript-supported example",
    }

    VAGUE_HEADINGS = {
        "introduction",
        "overview",
        "notes",
        "information",
        "details",
        "process",
        "definitions",
        "examples",
    }

    def __init__(
        self,
        min_bullet_words: int = 3,
        min_definition_words: int = 4,
        min_example_words: int = 4,
        min_paragraph_words: int = 5,
        min_summary_words: int = 4,
        min_section_content_items: int = 1,
        min_passing_score: int = 80,
    ) -> None:
        self.min_bullet_words = min_bullet_words
        self.min_definition_words = min_definition_words
        self.min_example_words = min_example_words
        self.min_paragraph_words = min_paragraph_words
        self.min_summary_words = min_summary_words
        self.min_section_content_items = min_section_content_items
        self.min_passing_score = min_passing_score
        self._validate_settings()

    def evaluate(self, notes: dict[str, Any], transcript: str | None = None,) -> dict[str, Any]:
        """Return content-quality errors, warnings, score, and pass status."""

        if not isinstance(notes, dict):
            raise TypeError("Structured notes must be a dictionary.")

        if transcript is not None and not isinstance(transcript, str):
            raise TypeError("Transcript must be a string or None.")

        errors: list[str] = []
        warnings: list[str] = []

        self._check_title_and_subtitle(notes, errors, warnings)
        self._check_sections(notes, errors, warnings)
        self._check_summary(notes, errors, warnings)

        if transcript and transcript.strip():
            self._check_transcript_coverage(
                notes=notes,
                transcript=transcript,
                warnings=warnings,
            )

        score = self._calculate_score(errors, warnings)
        passed = not errors and score >= self.min_passing_score

        if not errors and score < self.min_passing_score:
            errors.append(
                "The generated notes did not meet the minimum content-quality "
                f"score of {self.min_passing_score}."
            )
            score = self._calculate_score(errors, warnings)
            passed = False

        result = {
            "passed": passed,
            "score": score,
            "errors": errors,
            "warnings": warnings,
        }

        logger.info(
            "Content quality evaluation completed. Passed=%s, score=%d, "
            "errors=%d, warnings=%d.",
            passed,
            score,
            len(errors),
            len(warnings),
        )
        return result

    def require_usable(self, notes: dict[str, Any], transcript: str | None = None,) -> dict[str, Any]:
        """Raise an error when generated notes are not usable."""

        result = self.evaluate(notes, transcript)

        if not result["passed"]:
            problems = result["errors"] or [
                "The generated notes did not pass content-quality validation."
            ]

            raise ValueError(
                "Generated notes failed content-quality validation: "
                + "; ".join(problems)
            )
        return result

    def build_repair_feedback(self, quality_result: dict[str, Any],) -> str:
        """Create concise feedback for a quality-repair request."""

        if not isinstance(quality_result, dict):
            raise TypeError("Quality result must be a dictionary.")

        problems = []

        for error in quality_result.get("errors", []):
            problems.append(f"- ERROR: {error}")

        for warning in quality_result.get("warnings", []):
            problems.append(f"- WARNING: {warning}")

        if not problems:
            return "No content-quality problems were detected."

        return (
            "Rewrite the notes with specific, meaningful information from the "
            "transcript while preserving the exact JSON schema.\n"
            "Do not add facts that are not supported by the transcript.\n"
            "Do not use placeholder or sample wording.\n"
            "Every non-empty title, heading, paragraph, bullet, definition, "
            "example, and summary item must contain real transcript-based "
            "content.\n"
            "Use an empty array when a category has no useful content.\n\n"
            "Problems detected:\n"
            + "\n".join(problems)
        )

    def _check_title_and_subtitle(
        self,
        notes: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        title = self._clean_text(notes.get("title"))
        subtitle = self._clean_text(notes.get("subtitle"))

        if not title:
            errors.append("The note title is empty.")
        elif self._is_placeholder(title):
            errors.append(
                f"The note title is placeholder content: {title!r}."
            )
        elif self._word_count(title) < 2:
            warnings.append("The note title is unusually short.")

        if subtitle and self._is_placeholder(subtitle):
            errors.append(
                f"The note subtitle is placeholder content: {subtitle!r}."
            )

    def _check_sections(
        self,
        notes: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        sections = notes.get("sections")

        if not isinstance(sections, list) or not sections:
            errors.append("No usable note sections were generated.")
            return

        for section_index, section in enumerate(sections):
            prefix = f"Section {section_index + 1}"

            if not isinstance(section, dict):
                errors.append(f"{prefix} is invalid.")
                continue

            heading = self._clean_text(section.get("heading"))

            if not heading:
                errors.append(f"{prefix} has no heading.")
            elif self._is_placeholder(heading):
                errors.append(
                    f"{prefix} uses a placeholder heading: {heading!r}."
                )
            elif heading.lower() in self.VAGUE_HEADINGS:
                warnings.append(
                    f"{prefix} heading is very general: {heading!r}."
                )

            content_count = 0
            content_count += self._check_paragraphs(
                section, prefix, errors, warnings
            )
            content_count += self._check_bullets(
                section, prefix, errors, warnings
            )
            content_count += self._check_definitions(
                section, prefix, errors, warnings
            )
            content_count += self._check_examples(
                section, prefix, errors, warnings
            )

            if content_count < self.min_section_content_items:
                errors.append(f"{prefix} contains no meaningful content.")

    def _check_paragraphs(
        self,
        section: dict[str, Any],
        prefix: str,
        errors: list[str],
        warnings: list[str],
    ) -> int:
        paragraphs = section.get("paragraphs", [])
        meaningful_count = 0

        if not isinstance(paragraphs, list):
            return 0

        for index, paragraph in enumerate(paragraphs):
            text = self._clean_text(paragraph)

            if not text:
                continue

            label = f"{prefix} paragraph {index + 1}"

            if self._is_placeholder(text):
                errors.append(
                    f"{label} is placeholder content: {text!r}."
                )
                continue

            meaningful_count += 1

            if self._word_count(text) < self.min_paragraph_words:
                warnings.append(f"{label} is very short.")
        return meaningful_count

    def _check_bullets(
        self,
        section: dict[str, Any],
        prefix: str,
        errors: list[str],
        warnings: list[str],
    ) -> int:
        bullets = section.get("bullets", [])
        meaningful_count = 0

        if not isinstance(bullets, list):
            return 0

        for index, bullet in enumerate(bullets):
            if not isinstance(bullet, dict):
                continue

            text = self._clean_text(bullet.get("text"))

            if not text:
                continue

            label = f"{prefix} bullet {index + 1}"
            children = bullet.get("children", [])

            if self._is_placeholder(text):
                errors.append(
                    f"{label} is placeholder content: {text!r}."
                )
                continue

            meaningful_count += 1

            valid_child_found = False

            if isinstance(children, list):
                for child_index, child in enumerate(children):
                    child_text = self._clean_text(child)

                    if not child_text:
                        continue

                    child_label = (
                        f"{label} child {child_index + 1}"
                    )

                    if self._is_placeholder(child_text):
                        errors.append(
                            f"{child_label} is placeholder content: "
                            f"{child_text!r}."
                        )
                        continue

                    valid_child_found = True

                    if (
                        self._word_count(child_text)
                        < self.min_bullet_words
                    ):
                        warnings.append(
                            f"{child_label} is too short."
                        )

            if (
                self._word_count(text) < self.min_bullet_words
                and not valid_child_found
            ):
                warnings.append(
                    f"{label} is too short to explain a useful point."
                )
        return meaningful_count

    def _check_definitions(
        self,
        section: dict[str, Any],
        prefix: str,
        errors: list[str],
        warnings: list[str],
    ) -> int:
        definitions = section.get("definitions", [])
        meaningful_count = 0

        if not isinstance(definitions, list):
            return 0

        for index, definition in enumerate(definitions):
            if not isinstance(definition, dict):
                continue

            term = self._clean_text(definition.get("term"))
            meaning = self._clean_text(
                definition.get("definition")
            )

            if not term or not meaning:
                continue

            label = f"{prefix} definition {index + 1}"
            placeholder_found = False

            if self._is_placeholder(term):
                errors.append(
                    f"{label} uses a placeholder term: {term!r}."
                )
                placeholder_found = True

            if self._is_placeholder(meaning):
                errors.append(
                    f"{label} uses placeholder wording: {meaning!r}."
                )
                placeholder_found = True

            if placeholder_found:
                continue

            meaningful_count += 1

            if self._word_count(meaning) < self.min_definition_words:
                warnings.append(
                    f"{label} is too short to be useful."
                )
        return meaningful_count

    def _check_examples(
        self,
        section: dict[str, Any],
        prefix: str,
        errors: list[str],
        warnings: list[str],
    ) -> int:
        examples = section.get("examples", [])
        meaningful_count = 0

        if not isinstance(examples, list):
            return 0

        for index, example in enumerate(examples):
            text = self._clean_text(example)

            if not text:
                continue

            label = f"{prefix} example {index + 1}"

            if self._is_placeholder(text):
                errors.append(
                    f"{label} is placeholder content: {text!r}."
                )
                continue

            meaningful_count += 1

            if self._word_count(text) < self.min_example_words:
                warnings.append(
                    f"{label} is too short or vague."
                )
        return meaningful_count

    def _check_summary(
        self,
        notes: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        summary = notes.get("summary")

        if not isinstance(summary, list):
            errors.append("The final summary is invalid.")
            return

        if not summary:
            warnings.append("No final summary was generated.")
            return

        meaningful_items = 0

        for index, item in enumerate(summary):
            text = self._clean_text(item)
            label = f"Summary item {index + 1}"

            if not text:
                warnings.append(f"{label} is empty.")
                continue

            if self._is_placeholder(text):
                errors.append(
                    f"{label} is placeholder content: {text!r}."
                )
                continue

            meaningful_items += 1

            if self._word_count(text) < self.min_summary_words:
                warnings.append(f"{label} is very short.")

        if meaningful_items == 0:
            errors.append(
                "The final summary contains no meaningful content."
            )

    def _check_transcript_coverage(
        self,
        notes: dict[str, Any],
        transcript: str,
        warnings: list[str],
    ) -> None:
        """Estimate whether notes are disproportionately short."""

        transcript_words = self._word_count(transcript)
        note_words = self._word_count(
            self._flatten_notes(notes)
        )

        if transcript_words < 50:
            return

        coverage_ratio = note_words / max(
            transcript_words,
            1,
        )

        if coverage_ratio < 0.15:
            warnings.append(
                "The generated notes are very short compared with the "
                f"transcript (approximate coverage ratio: "
                f"{coverage_ratio:.2f})."
            )
        elif coverage_ratio < 0.25:
            warnings.append(
                "The generated notes may omit important transcript content "
                f"(approximate coverage ratio: {coverage_ratio:.2f})."
            )

    def _flatten_notes(self, notes: dict[str, Any],) -> str:
        values = [
            self._clean_text(notes.get("title")),
            self._clean_text(notes.get("subtitle")),
        ]

        sections = notes.get("sections", [])

        if not isinstance(sections, list):
            sections = []

        for section in sections:
            if not isinstance(section, dict):
                continue

            values.append(
                self._clean_text(section.get("heading"))
            )

            for paragraph in section.get("paragraphs", []):
                values.append(self._clean_text(paragraph))

            for bullet in section.get("bullets", []):
                if not isinstance(bullet, dict):
                    continue

                values.append(
                    self._clean_text(bullet.get("text"))
                )

                for child in bullet.get("children", []):
                    values.append(self._clean_text(child))

            for definition in section.get(
                "definitions",
                [],
            ):
                if not isinstance(definition, dict):
                    continue

                values.append(
                    self._clean_text(definition.get("term"))
                )
                values.append(
                    self._clean_text(
                        definition.get("definition")
                    )
                )

            for example in section.get("examples", []):
                values.append(self._clean_text(example))

        summary = notes.get("summary", [])

        if isinstance(summary, list):
            for item in summary:
                values.append(self._clean_text(item))

        return " ".join(
            value for value in values if value
        )

    def _calculate_score(self, errors: list[str], warnings: list[str],) -> int:
        score = (
            100
            - len(errors) * 20
            - len(warnings) * 5
        )

        return max(0, min(100, score))

    def _is_placeholder(self, text: str) -> bool:
        """Detect explicit, generic, and numbered placeholders."""

        normalized = re.sub(
            r"\s+",
            " ",
            text.strip().lower(),
        )
        normalized = normalized.strip(" .:-_")

        if not normalized:
            return False

        if normalized in self.PLACEHOLDER_VALUES:
            return True

        if normalized.startswith(
            (
                "insert ",
                "add ",
                "write ",
                "example here",
                "definition here",
                "placeholder",
            )
        ):
            return True

        placeholder_patterns = (
            r"^(example\s+)?title(?:\s+\d+)?$",
            r"^(example\s+)?subtitle(?:\s+\d+)?$",
            r"^(example\s+)?section(?:\s+heading)?(?:\s+\d+)?$",
            r"^(main\s+)?bullet(?:\s+point)?(?:\s+\d+)?$",
            r"^nested\s+(?:bullet|supporting\s+point)(?:\s+\d+)?$",
            r"^(?:technical\s+)?term(?:\s+\d+)?$",
            r"^(?:example\s+)?definition(?:\s+\d+)?$",
            r"^(?:example|explanatory)\s+paragraph(?:\s+\d+)?$",
            r"^(?:final|important\s+final)?\s*"
            r"(?:summary|takeaway)(?:\s+\d+)?$",
        )

        return any(
            re.fullmatch(pattern, normalized)
            for pattern in placeholder_patterns
        )

    def _clean_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return re.sub(r"\s+", " ", value).strip()

    def _word_count(self, text: str) -> int:
        return len(
            re.findall(
                r"\b[\w'-]+\b",
                text,
            )
        )

    def _validate_settings(self) -> None:
        integer_settings = {
            "min_bullet_words": self.min_bullet_words,
            "min_definition_words": self.min_definition_words,
            "min_example_words": self.min_example_words,
            "min_paragraph_words": self.min_paragraph_words,
            "min_summary_words": self.min_summary_words,
            "min_section_content_items": (
                self.min_section_content_items
            ),
            "min_passing_score": self.min_passing_score,
        }

        for name, value in integer_settings.items():
            if not isinstance(value, int):
                raise TypeError(
                    f"{name} must be an integer."
                )

        for name, value in integer_settings.items():
            if name == "min_passing_score":
                if not 0 <= value <= 100:
                    raise ValueError(
                        "min_passing_score must be between 0 and 100."
                    )
            elif value < 1:
                raise ValueError(
                    f"{name} must be at least 1."
                )
