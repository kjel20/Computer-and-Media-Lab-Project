import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

class ContentQualityValidator:
    """Checks whether structured lecture notes contain useful, meaningful content."""

    PLACEHOLDER_VALUES = {
        "example",
        "examples",
        "definition",
        "definitions",
        "main bullet",
        "main bullet point",
        "bullet point",
        "nested bullet",
        "supporting point",
        "section",
        "section heading",
        "lecture title",
        "lecture notes",
        "summary",
        "final takeaway",
        "important takeaway",
        "term",
        "meaning",
        "issue",
        "explanatory paragraph",
        "explanatory paragraph based on the transcript",
        "paragraph based on the transcript",
        "example supported by the transcript",
        "for example, example supported by the transcript",
        "transcript-supported example",
    }

    VAGUE_HEADINGS = {
        "introduction",
        "overview",
        "notes",
        "section",
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
    ) -> None:
        self.min_bullet_words = min_bullet_words
        self.min_definition_words = min_definition_words
        self.min_example_words = min_example_words
        self.min_paragraph_words = min_paragraph_words
        self.min_summary_words = min_summary_words
        self.min_section_content_items = min_section_content_items
        self._validate_settings()

    def evaluate(self, notes: dict[str, Any], transcript: str | None = None) -> dict[str, Any]:
        """
        Evaluate structured notes and return errors, warnings, and a score.

        Errors represent clearly unusable content.
        Warnings represent weak but potentially usable content.
        """

        if not isinstance(notes, dict):
            raise TypeError("Structured notes must be a dictionary.")

        if transcript is not None and not isinstance(transcript, str):
            raise TypeError("Transcript must be a string or None.")

        errors: list[str] = []
        warnings: list[str] = []

        self._check_title(notes, errors, warnings)
        self._check_sections(notes, errors, warnings)
        self._check_summary(notes, errors, warnings)

        if transcript and transcript.strip():
            self._check_transcript_coverage(
                notes=notes,
                transcript=transcript,
                warnings=warnings,
            )

        score = self._calculate_score(errors, warnings)

        result = {
            "passed": len(errors) == 0,
            "score": score,
            "errors": errors,
            "warnings": warnings,
        }

        logger.info(
            "Content quality evaluation completed. Passed=%s, score=%d, "
            "errors=%d, warnings=%d.",
            result["passed"],
            result["score"],
            len(errors),
            len(warnings),
        )
        return result

    def require_usable(self, notes: dict[str, Any], transcript: str | None = None) -> dict[str, Any]:
        """Raise an error when clearly unusable content is found."""

        result = self.evaluate(notes, transcript)

        if result["errors"]:
            raise ValueError(
                "Generated notes failed content-quality validation: "
                + "; ".join(result["errors"])
            )
        return result

    def build_repair_feedback(self, quality_result: dict[str, Any]) -> str:
        """Create concise feedback for one optional quality-repair request."""

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
            "Improve the note content while preserving the JSON schema.\n"
            "Do not add facts outside the transcript.\n\n"
            "Problems detected:\n"
            + "\n".join(problems)
        )

    def _check_title(
        self,
        notes: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        title = self._clean_text(notes.get("title"))

        if not title:
            errors.append("The note title is empty.")
            return

        if self._is_placeholder(title):
            errors.append(f"The note title is a placeholder: {title!r}.")
        elif self._word_count(title) < 2:
            warnings.append("The note title is unusually short.")

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
            if not isinstance(section, dict):
                errors.append(f"Section {section_index + 1} is invalid.")
                continue

            heading = self._clean_text(section.get("heading"))
            prefix = f"Section {section_index + 1}"

            if not heading:
                errors.append(f"{prefix} has no heading.")
            elif self._is_placeholder(heading):
                warnings.append(f"{prefix} uses a vague or placeholder heading: {heading!r}.")
            elif heading.lower() in self.VAGUE_HEADINGS:
                warnings.append(f"{prefix} heading is very general: {heading!r}.")

            content_count = 0
            content_count += self._check_paragraphs(section, prefix, warnings)
            content_count += self._check_bullets(section, prefix, errors, warnings)
            content_count += self._check_definitions(section, prefix, errors, warnings)
            content_count += self._check_examples(section, prefix, errors, warnings)

            if content_count < self.min_section_content_items:
                errors.append(f"{prefix} contains no meaningful content.")

    def _check_paragraphs(
        self,
        section: dict[str, Any],
        prefix: str,
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

            meaningful_count += 1

            if self._is_placeholder(text):
                warnings.append(
                    f"{prefix} paragraph {index + 1} appears to be placeholder text."
                )
            elif self._word_count(text) < self.min_paragraph_words:
                warnings.append(
                    f"{prefix} paragraph {index + 1} is very short."
                )
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

            meaningful_count += 1
            label = f"{prefix} bullet {index + 1}"

            if self._is_placeholder(text):
                errors.append(f"{label} is placeholder or vague text: {text!r}.")
            elif (
                self._word_count(text) < self.min_bullet_words
                and not any(
                    self._word_count(self._clean_text(child))
                    >= self.min_bullet_words
                    for child in bullet.get("children", [])
                    if isinstance(child, str)
                )
            ):
                warnings.append(
                    f"{label} is too short to explain a useful point."
                )

            children = bullet.get("children", [])

            if not isinstance(children, list):
                continue

            for child_index, child in enumerate(children):
                child_text = self._clean_text(child)

                if not child_text:
                    continue

                if self._is_placeholder(child_text):
                    errors.append(
                        f"{label} child {child_index + 1} is placeholder text: "
                        f"{child_text!r}."
                    )
                elif self._word_count(child_text) < self.min_bullet_words:
                    warnings.append(
                        f"{label} child {child_index + 1} is too short."
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
            meaning = self._clean_text(definition.get("definition"))

            if not term or not meaning:
                continue

            meaningful_count += 1
            label = f"{prefix} definition {index + 1}"

            if self._is_placeholder(term):
                errors.append(f"{label} uses a placeholder term: {term!r}.")

            if self._is_placeholder(meaning):
                errors.append(f"{label} uses placeholder wording: {meaning!r}.")
            elif self._word_count(meaning) < self.min_definition_words:
                warnings.append(f"{label} is too short to be useful.")
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

            meaningful_count += 1
            label = f"{prefix} example {index + 1}"

            if self._is_placeholder(text):
                errors.append(f"{label} is placeholder text: {text!r}.")
            elif self._word_count(text) < self.min_example_words:
                warnings.append(f"{label} is too short or vague.")
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

        for index, item in enumerate(summary):
            text = self._clean_text(item)

            if not text:
                warnings.append(f"Summary item {index + 1} is empty.")
            elif self._is_placeholder(text):
                errors.append(f"Summary item {index + 1} is placeholder text.")
            elif self._word_count(text) < self.min_summary_words:
                warnings.append(f"Summary item {index + 1} is very short.")

    def _check_transcript_coverage(
        self,
        notes: dict[str, Any],
        transcript: str,
        warnings: list[str],
    ) -> None:
        """
        Estimate whether the generated notes are disproportionately short.

        This is intentionally simple. It does not judge semantic correctness.
        """

        transcript_words = self._word_count(transcript)
        note_words = self._word_count(self._flatten_notes(notes))

        if transcript_words < 50:
            return

        coverage_ratio = note_words / max(transcript_words, 1)

        if coverage_ratio < 0.15:
            warnings.append(
                "The generated notes are very short compared with the transcript "
                f"(approximate coverage ratio: {coverage_ratio:.2f})."
            )
        elif coverage_ratio < 0.25:
            warnings.append(
                "The generated notes may omit important transcript content "
                f"(approximate coverage ratio: {coverage_ratio:.2f})."
            )

    def _flatten_notes(self, notes: dict[str, Any]) -> str:
        values = [
            self._clean_text(notes.get("title")),
            self._clean_text(notes.get("subtitle")),
        ]

        for section in notes.get("sections", []):
            if not isinstance(section, dict):
                continue

            values.append(self._clean_text(section.get("heading")))

            for paragraph in section.get("paragraphs", []):
                values.append(self._clean_text(paragraph))

            for bullet in section.get("bullets", []):
                if not isinstance(bullet, dict):
                    continue

                values.append(self._clean_text(bullet.get("text")))

                for child in bullet.get("children", []):
                    values.append(self._clean_text(child))

            for definition in section.get("definitions", []):
                if not isinstance(definition, dict):
                    continue

                values.append(self._clean_text(definition.get("term")))
                values.append(self._clean_text(definition.get("definition")))

            for example in section.get("examples", []):
                values.append(self._clean_text(example))

        for summary_item in notes.get("summary", []):
            values.append(self._clean_text(summary_item))

        return " ".join(value for value in values if value)

    def _calculate_score(self, errors: list[str], warnings: list[str]) -> int:
        score = 100 - len(errors) * 20 - len(warnings) * 5
        return max(0, min(100, score))

    def _is_placeholder(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        normalized = normalized.strip(" .:-_")

        if normalized in self.PLACEHOLDER_VALUES:
            return True

        return normalized.startswith((
            "insert ",
            "add ",
            "write ",
            "example here",
            "definition here",
            "placeholder",
        ))

    def _clean_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return re.sub(r"\s+", " ", value).strip()

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"\b[\w'-]+\b", text))

    def _validate_settings(self) -> None:
        settings = {
            "min_bullet_words": self.min_bullet_words,
            "min_definition_words": self.min_definition_words,
            "min_example_words": self.min_example_words,
            "min_paragraph_words": self.min_paragraph_words,
            "min_summary_words": self.min_summary_words,
            "min_section_content_items": self.min_section_content_items,
        }

        for name, value in settings.items():
            if not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")

            if value < 1:
                raise ValueError(f"{name} must be at least 1.")