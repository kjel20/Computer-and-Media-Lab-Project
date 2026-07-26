import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

EMPTY_NOTE_DOCUMENT = {
    "title": "Lecture Notes",
    "subtitle": "",
    "sections": [],
    "summary": [],
}

class NoteSchema:
    """Validates and normalizes structured lecture-note data."""

    def normalize(self, data: Any) -> dict[str, Any]:
        """
        Convert generated data into the expected note structure.

        Missing optional fields are added automatically.
        Invalid values are replaced or skipped safely.
        """

        if not isinstance(data, dict):
            raise TypeError("Generated note data must be a dictionary.")

        normalized = copy.deepcopy(EMPTY_NOTE_DOCUMENT)

        normalized["title"] = self._clean_required_text(
            data.get("title"),
            fallback="Lecture Notes",
        )

        normalized["subtitle"] = self._clean_optional_text(
            data.get("subtitle")
        )

        normalized["sections"] = self._normalize_sections(
            data.get("sections", [])
        )

        normalized["summary"] = self._normalize_string_list(
            data.get("summary", [])
        )

        if not normalized["sections"]:
            logger.warning(
                "Generated note data contained no valid sections."
            )

        return normalized

    def validate(self, data: Any) -> tuple[bool, list[str]]:
        """
        Check whether data already follows the expected schema.

        Returns
        -------
        tuple
            True or False, followed by a list of problems.
        """

        errors: list[str] = []

        if not isinstance(data, dict):
            return False, [
                "The root JSON value must be an object."
            ]

        if not isinstance(data.get("title"), str):
            errors.append(
                "The title must be a string."
            )
        elif not data["title"].strip():
            errors.append(
                "The title cannot be empty."
            )

        if "subtitle" in data and not isinstance(
            data["subtitle"],
            str,
        ):
            errors.append(
                "The subtitle must be a string."
            )

        sections = data.get("sections")

        if not isinstance(sections, list):
            errors.append(
                "Sections must be a list."
            )
        else:
            for index, section in enumerate(sections):
                errors.extend(
                    self._validate_section(
                        section,
                        index,
                    )
                )

        summary = data.get("summary")

        if not isinstance(summary, list):
            errors.append(
                "Summary must be a list."
            )
        else:
            for index, item in enumerate(summary):
                if not isinstance(item, str):
                    errors.append(
                        f"Summary item {index} must be a string."
                    )

        return len(errors) == 0, errors

    def create_empty_document(self) -> dict[str, Any]:
        """Return a new empty note document."""

        return copy.deepcopy(
            EMPTY_NOTE_DOCUMENT
        )

    def _normalize_sections(self, sections: Any) -> list[dict[str, Any]]:
        if not isinstance(sections, list):
            logger.warning(
                "Sections were not provided as a list."
            )
            return []

        normalized_sections = []

        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                logger.warning(
                    "Skipping section %d because it is not an object.",
                    index,
                )
                continue

            normalized_section = self._normalize_section(
                section
            )

            if self._section_has_content(
                normalized_section
            ):
                normalized_sections.append(
                    normalized_section
                )
            else:
                logger.warning(
                    "Skipping empty section %d.",
                    index,
                )

        return normalized_sections

    def _normalize_section(self, section: dict[str, Any]) -> dict[str, Any]:
        return {
            "heading": self._clean_required_text(
                section.get("heading"),
                fallback="Section",
            ),
            "paragraphs": self._normalize_string_list(
                section.get("paragraphs", [])
            ),
            "bullets": self._normalize_bullets(
                section.get("bullets", [])
            ),
            "definitions": self._normalize_definitions(
                section.get("definitions", [])
            ),
            "examples": self._normalize_string_list(
                section.get("examples", [])
            ),
        }

    def _normalize_bullets(self, bullets: Any) -> list[dict[str, Any]]:
        if not isinstance(bullets, list):
            return []

        normalized_bullets = []

        for index, bullet in enumerate(bullets):
            if isinstance(bullet, str):
                text = bullet.strip()

                if text:
                    normalized_bullets.append({
                        "text": text,
                        "children": [],
                    })
                continue

            if not isinstance(bullet, dict):
                logger.warning(
                    "Skipping bullet %d because it is invalid.",
                    index,
                )
                continue

            text = self._clean_optional_text(
                bullet.get("text")
            )

            if not text:
                logger.warning(
                    "Skipping bullet %d because it has no text.",
                    index,
                )
                continue

            children = self._normalize_string_list(
                bullet.get("children", [])
            )

            normalized_bullets.append({
                "text": text,
                "children": children,
            })
        return normalized_bullets

    def _normalize_definitions(self, definitions: Any) -> list[dict[str, str]]:
        if not isinstance(definitions, list):
            return []

        normalized_definitions = []

        for index, definition in enumerate(definitions):
            if not isinstance(definition, dict):
                logger.warning(
                    "Skipping definition %d because it is invalid.",
                    index,
                )
                continue

            term = self._clean_optional_text(
                definition.get("term")
            )

            meaning = self._clean_optional_text(
                definition.get("definition")
            )

            if not term or not meaning:
                logger.warning(
                    "Skipping definition %d because its term "
                    "or definition is missing.",
                    index,
                )
                continue

            normalized_definitions.append({
                "term": term,
                "definition": meaning,
            })
        return normalized_definitions

    def _normalize_string_list(self, values: Any) -> list[str]:
        if isinstance(values, str):
            values = [values]

        if not isinstance(values, list):
            return []

        cleaned_values = []

        for value in values:
            if not isinstance(value, str):
                continue

            value = value.strip()

            if value:
                cleaned_values.append(value)

        return cleaned_values

    def _validate_section(self, section: Any, index: int) -> list[str]:
        errors = []
        prefix = f"Section {index}"

        if not isinstance(section, dict):
            return [
                f"{prefix} must be an object."
            ]

        heading = section.get("heading")

        if not isinstance(heading, str):
            errors.append(
                f"{prefix} heading must be a string."
            )
        elif not heading.strip():
            errors.append(
                f"{prefix} heading cannot be empty."
            )

        for key in (
            "paragraphs",
            "bullets",
            "definitions",
            "examples",
        ):
            if key not in section:
                errors.append(
                    f"{prefix} is missing '{key}'."
                )
            elif not isinstance(
                section[key],
                list,
            ):
                errors.append(
                    f"{prefix} '{key}' must be a list."
                )

        if isinstance(
            section.get("paragraphs"),
            list,
        ):
            for item_index, paragraph in enumerate(
                section["paragraphs"]
            ):
                if not isinstance(paragraph, str):
                    errors.append(
                        f"{prefix} paragraph {item_index} "
                        "must be a string."
                    )

        if isinstance(
            section.get("examples"),
            list,
        ):
            for item_index, example in enumerate(
                section["examples"]
            ):
                if not isinstance(example, str):
                    errors.append(
                        f"{prefix} example {item_index} "
                        "must be a string."
                    )

        if isinstance(
            section.get("bullets"),
            list,
        ):
            for bullet_index, bullet in enumerate(
                section["bullets"]
            ):
                errors.extend(
                    self._validate_bullet(
                        bullet,
                        index,
                        bullet_index,
                    )
                )

        if isinstance(
            section.get("definitions"),
            list,
        ):
            for definition_index, definition in enumerate(
                section["definitions"]
            ):
                errors.extend(
                    self._validate_definition(
                        definition,
                        index,
                        definition_index,
                    )
                )

        return errors

    def _validate_bullet(self, bullet: Any, section_index: int, bullet_index: int,) -> list[str]:
        prefix = (
            f"Section {section_index} "
            f"bullet {bullet_index}"
        )

        if not isinstance(bullet, dict):
            return [
                f"{prefix} must be an object."
            ]

        errors = []

        if not isinstance(
            bullet.get("text"),
            str,
        ):
            errors.append(
                f"{prefix} text must be a string."
            )
        elif not bullet["text"].strip():
            errors.append(
                f"{prefix} text cannot be empty."
            )

        children = bullet.get("children")

        if not isinstance(children, list):
            errors.append(
                f"{prefix} children must be a list."
            )
        else:
            for child_index, child in enumerate(children):
                if not isinstance(child, str):
                    errors.append(
                        f"{prefix} child {child_index} "
                        "must be a string."
                    )

        return errors

    def _validate_definition(self, definition: Any, section_index: int, definition_index: int,) -> list[str]:
        prefix = (
            f"Section {section_index} "
            f"definition {definition_index}"
        )

        if not isinstance(definition, dict):
            return [
                f"{prefix} must be an object."
            ]

        errors = []

        for key in ("term", "definition"):
            value = definition.get(key)

            if not isinstance(value, str):
                errors.append(
                    f"{prefix} '{key}' must be a string."
                )
            elif not value.strip():
                errors.append(
                    f"{prefix} '{key}' cannot be empty."
                )
        return errors

    def _section_has_content(self, section: dict[str, Any]) -> bool:
        return any([
            section["paragraphs"],
            section["bullets"],
            section["definitions"],
            section["examples"],
        ])

    def _clean_required_text(self, value: Any, fallback: str) -> str:
        if not isinstance(value, str):
            return fallback

        value = value.strip()
        return value or fallback

    def _clean_optional_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()