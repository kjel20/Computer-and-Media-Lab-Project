import json
import logging
from typing import Any
from src.note_schema import NoteSchema
from src.prompt_templates import (
    FACTUAL_SOURCE_RULES_TEMPLATE,
    FINAL_CHECK_TEMPLATE,
    HALLUCINATION_PREVENTION_TEMPLATE,
    JSON_OUTPUT_RULES_TEMPLATE,
    NOTE_GENERATION_TASK_TEMPLATE,
    REFERENCE_EXAMPLES_INTRO_TEMPLATE,
    SCHEMA_INTRO_TEMPLATE,
    STYLE_IMITATION_RULES_TEMPLATE,
    STYLE_PROFILE_INTRO_TEMPLATE,
    SYSTEM_ROLE_TEMPLATE,
    TRANSCRIPT_INTRO_TEMPLATE,
)

logger = logging.getLogger(__name__)

class PromptBuilder:
    """Builds the final structured note-generation prompt."""

    def __init__(
        self,
        max_transcript_chars: int = 18000,
        max_reference_chars: int = 5000,
        max_chunk_chars: int = 1500,
        max_reference_chunks: int = 4,
    ) -> None:
        self.max_transcript_chars = max_transcript_chars
        self.max_reference_chars = max_reference_chars
        self.max_chunk_chars = max_chunk_chars
        self.max_reference_chunks = max_reference_chunks
        self.schema = NoteSchema()
        self._validate_limits()

    def build_prompt(
        self,
        edited_transcript: str,
        retrieved_chunks: list[dict[str, Any]],
        resolved_style_profile: dict[str, Any],
    ) -> str:
        """Return the complete prompt sent to Ollama."""

        transcript = self._validate_transcript(edited_transcript)
        chunks = self._validate_chunks(retrieved_chunks)
        profile = self._validate_style_profile(resolved_style_profile)

        transcript_text = self._truncate_text(
            transcript,
            self.max_transcript_chars,
            label="transcript",
        )

        reference_text = self._format_reference_chunks(chunks)
        style_summary = self._summarize_style_profile(profile)
        schema_text = self.get_schema_text()

        sections = [
            SYSTEM_ROLE_TEMPLATE,
            self._section("TASK", NOTE_GENERATION_TASK_TEMPLATE),
            self._section("FACTUAL SOURCE RULES", FACTUAL_SOURCE_RULES_TEMPLATE),
            self._section("STYLE IMITATION RULES", STYLE_IMITATION_RULES_TEMPLATE),
            self._section("ACCURACY RULES", HALLUCINATION_PREVENTION_TEMPLATE),
            self._section(
                "REFERENCE NOTE EXAMPLES",
                f"{REFERENCE_EXAMPLES_INTRO_TEMPLATE}\n\n{reference_text}",
            ),
            self._section(
                "RESOLVED STYLE SUMMARY",
                f"{STYLE_PROFILE_INTRO_TEMPLATE}\n\n{style_summary}",
            ),
            self._section(
                "EDITED LECTURE TRANSCRIPT",
                f"{TRANSCRIPT_INTRO_TEMPLATE}\n\n{transcript_text}",
            ),
            self._section(
                "REQUIRED JSON SCHEMA",
                f"{SCHEMA_INTRO_TEMPLATE}\n\n{schema_text}",
            ),
            self._section("JSON OUTPUT RULES", JSON_OUTPUT_RULES_TEMPLATE),
            self._section("FINAL CHECK", FINAL_CHECK_TEMPLATE),
        ]

        prompt = "\n\n".join(section.strip() for section in sections if section.strip())

        logger.info(
            "Prompt built with %d transcript characters, %d reference chunk(s), "
            "and %d total characters.",
            len(transcript_text),
            len(chunks[:self.max_reference_chunks]),
            len(prompt),
        )

        return prompt

    def get_schema_text(self) -> str:
        """Return the required JSON structure as formatted text."""

        schema_example = {
            "title": "",
            "subtitle": "",
            "sections": [
                {
                    "heading": "",
                    "paragraphs": [],
                    "bullets": [],
                    "definitions": [],
                    "examples": [],
                }
            ],
            "summary": [],
        }

        return json.dumps(
            schema_example,
            indent=2,
            ensure_ascii=False,
        )

    def _format_reference_chunks(self, chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks while enforcing safe prompt limits."""

        if not chunks:
            return (
                "No reference-note excerpts were available. "
                "Use a clear, concise lecture-note structure."
            )

        formatted_chunks = []
        used_characters = 0

        for rank, chunk in enumerate(chunks[:self.max_reference_chunks], start=1):
            text = self._truncate_text(
                chunk["text"],
                self.max_chunk_chars,
                label=f"reference chunk {rank}",
            )

            source = str(chunk.get("source", "unknown"))
            chunk_id = chunk.get("chunk_id", "unknown")
            score = chunk.get("score")

            header = [
                f"REFERENCE EXAMPLE {rank}",
                f"Source: {source}",
                f"Chunk ID: {chunk_id}",
            ]

            if isinstance(score, (int, float)):
                header.append(f"Similarity score: {score:.4f}")

            entry = "\n".join(header) + f"\n\n{text}"

            if used_characters + len(entry) > self.max_reference_chars:
                remaining = self.max_reference_chars - used_characters

                if remaining > 200:
                    formatted_chunks.append(
                        self._truncate_text(
                            entry,
                            remaining,
                            label="reference examples",
                        )
                    )
                break

            formatted_chunks.append(entry)
            used_characters += len(entry)

        return "\n\n---\n\n".join(formatted_chunks)

    def _summarize_style_profile(self, profile: dict[str, Any]) -> str:
        """Convert the resolved profile into short, useful prompt instructions."""

        body = profile.get("body", {})
        title = profile.get("title", {})
        heading_1 = profile.get("heading_1", {})
        heading_2 = profile.get("heading_2", {})
        heading_3 = profile.get("heading_3", {})
        bullet = profile.get("bullet", {})
        page = profile.get("page", {})

        lines = [
            "Use a clear hierarchy of title, section headings, paragraphs, and bullets.",
            (
                f"Body style: {body.get('font', 'default font')}, "
                f"{body.get('font_size', 'unknown')} pt, "
                f"bold={body.get('bold', False)}, "
                f"italic={body.get('italic', False)}."
            ),
            (
                f"Title style: {title.get('font', body.get('font', 'default font'))}, "
                f"{title.get('font_size', 'unknown')} pt, "
                f"bold={title.get('bold', True)}."
            ),
            (
                f"Heading hierarchy: Heading 1={heading_1.get('font_size', 'unknown')} pt, "
                f"Heading 2={heading_2.get('font_size', 'unknown')} pt, "
                f"Heading 3={heading_3.get('font_size', 'unknown')} pt."
            ),
            (
                f"Bullet indentation: {bullet.get('indent_left', 'unknown')} pt, "
                f"nested increment={bullet.get('nested_indent_increment', 'unknown')} pt."
            ),
            (
                f"Body line-spacing ratio: "
                f"{body.get('line_spacing_ratio', 'unknown')}."
            ),
            (
                f"Paragraph spacing after: "
                f"{body.get('paragraph_spacing_after', 'unknown')} pt."
            ),
            (
                f"Page margins: left={page.get('margin_left', 'unknown')} pt, "
                f"right={page.get('margin_right', 'unknown')} pt, "
                f"top={page.get('margin_top', 'unknown')} pt, "
                f"bottom={page.get('margin_bottom', 'unknown')} pt."
            ),
            (
                "Use these values only as organizational guidance. "
                "Do not mention fonts, points, margins, colors, or indentation "
                "inside the generated note content."
            ),
        ]

        return "\n".join(f"- {line}" for line in lines)

    def _validate_transcript(self, transcript: str) -> str:
        if not isinstance(transcript, str):
            raise TypeError("Edited transcript must be a string.")

        transcript = transcript.strip()

        if not transcript:
            raise ValueError("Edited transcript cannot be empty.")

        return transcript

    def _validate_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(chunks, list):
            raise TypeError("Retrieved chunks must be provided as a list.")

        valid_chunks = []

        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                logger.warning(
                    "Skipping retrieved chunk %d because it is not a dictionary.",
                    index,
                )
                continue

            text = chunk.get("text", "")

            if not isinstance(text, str) or not text.strip():
                logger.warning(
                    "Skipping retrieved chunk %d because it contains no usable text.",
                    index,
                )
                continue

            chunk_copy = chunk.copy()
            chunk_copy["text"] = text.strip()
            valid_chunks.append(chunk_copy)

        return valid_chunks

    def _validate_style_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(profile, dict):
            raise TypeError("Resolved style profile must be a dictionary.")

        required_sections = (
            "page",
            "body",
            "title",
            "heading_1",
            "heading_2",
            "heading_3",
            "bullet",
        )

        missing = [
            section
            for section in required_sections
            if not isinstance(profile.get(section), dict)
        ]

        if missing:
            raise ValueError(
                "Resolved style profile is missing valid sections: "
                + ", ".join(missing)
            )

        return profile

    def _validate_limits(self) -> None:
        limits = {
            "max_transcript_chars": self.max_transcript_chars,
            "max_reference_chars": self.max_reference_chars,
            "max_chunk_chars": self.max_chunk_chars,
            "max_reference_chunks": self.max_reference_chunks,
        }

        for name, value in limits.items():
            if not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")

            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        if self.max_chunk_chars > self.max_reference_chars:
            raise ValueError(
                "max_chunk_chars cannot be larger than max_reference_chars."
            )

    def _truncate_text(self, text: str, maximum: int, label: str) -> str:
        """Shorten text without ending in the middle of a word."""

        if len(text) <= maximum:
            return text

        shortened = text[:maximum]
        last_space = shortened.rfind(" ")

        if last_space > maximum * 0.80:
            shortened = shortened[:last_space]

        logger.warning(
            "%s exceeded %d characters and was truncated.",
            label.capitalize(),
            maximum,
        )

        return shortened.rstrip() + "\n[Content truncated because of prompt limits.]"

    def _section(self, title: str, content: str) -> str:
        border = "=" * 72
        return f"{border}\n{title}\n{border}\n\n{content.strip()}"