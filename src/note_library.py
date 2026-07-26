import logging
import re
from pathlib import Path
from typing import Any
import pymupdf
from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    NOTES_DIR,
    SUPPORTED_NOTE_EXTENSIONS,
)

logger = logging.getLogger(__name__)

class NoteLibrary:
    """
    Loads previous note files, extracts their text,
    cleans it, and divides it into overlapping chunks.

    TXT and PDF files are supported.
    """

    def __init__(self, notes_dir: Path = NOTES_DIR, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP,) -> None:
        """
        Create a note library.

        Parameters
        ----------
        notes_dir:
            Directory containing previous note files.

        chunk_size:
            Approximate maximum number of characters
            in each chunk.

        chunk_overlap:
            Number of characters repeated between
            neighboring chunks.
        """

        self.notes_dir = Path(notes_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._validate_chunk_settings()
        self.notes_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _validate_chunk_settings(self) -> None:
        """
        Ensure the chunk settings are safe.
        """

        if not isinstance(self.chunk_size, int):
            raise TypeError(
                "Chunk size must be an integer."
            )

        if not isinstance(self.chunk_overlap, int):
            raise TypeError(
                "Chunk overlap must be an integer."
            )

        if self.chunk_size <= 0:
            raise ValueError(
                "Chunk size must be greater than zero."
            )

        if self.chunk_overlap < 0:
            raise ValueError(
                "Chunk overlap cannot be negative."
            )

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "Chunk overlap must be smaller "
                "than chunk size."
            )

    def get_note_files(self) -> list[Path]:
        """
        Return all supported note files.

        Returns
        -------
        list[Path]
            Supported files sorted by filename.
        """

        if not self.notes_dir.exists():
            logger.warning(
                "Notes directory does not exist: %s",
                self.notes_dir,
            )
            return []

        files: list[Path] = []

        try:
            directory_items = self.notes_dir.iterdir()

        except OSError:
            logger.exception(
                "Could not access notes directory: %s",
                self.notes_dir,
            )
            return []

        for file_path in directory_items:
            if not file_path.is_file():
                continue

            if (
                file_path.suffix.lower()
                in SUPPORTED_NOTE_EXTENSIONS
            ):
                files.append(file_path)

        files.sort(
            key=lambda path: path.name.lower()
        )

        logger.info(
            "Found %d supported note file(s).",
            len(files),
        )
        return files

    def load_all_notes(self) -> list[dict[str, Any]]:
        """
        Load every usable note file.

        Invalid or empty files are skipped.
        """

        note_files = self.get_note_files()

        if not note_files:
            logger.warning(
                "No supported notes were found in %s.",
                self.notes_dir,
            )
            return []

        notes: list[dict[str, Any]] = []

        for file_path in note_files:
            note = self.load_note(file_path)

            if note is not None:
                notes.append(note)

        logger.info(
            "Loaded %d usable note file(s).",
            len(notes),
        )
        return notes

    def load_note(self, file_path: Path,) -> dict[str, Any] | None:
        """
        Load and clean one TXT or PDF file.

        Returns
        -------
        dict | None
            Loaded note data, or None if the file
            cannot be used.
        """

        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(
                "Note file does not exist: %s",
                file_path,
            )
            return None

        if not file_path.is_file():
            logger.warning(
                "Note path is not a file: %s",
                file_path,
            )
            return None

        extension = file_path.suffix.lower()

        if extension not in SUPPORTED_NOTE_EXTENSIONS:
            logger.warning(
                "Unsupported note file skipped: %s",
                file_path.name,
            )
            return None

        try:
            if extension == ".txt":
                raw_text = self._read_text_file(
                    file_path
                )
            elif extension == ".pdf":
                raw_text = self._read_pdf_file(
                    file_path
                )
            else:
                return None

        except Exception:
            logger.exception(
                "Could not read note file: %s",
                file_path.name,
            )
            return None

        cleaned_text = self.clean_text(raw_text)

        if not cleaned_text:
            logger.warning(
                "No usable text was extracted from %s.",
                file_path.name,
            )
            return None

        return {
            "text": cleaned_text,
            "source": file_path.name,
            "path": file_path,
            "file_type": extension,
        }

    def _read_text_file(self, file_path: Path,) -> str:
        """
        Read a normal text file.
        """

        try:
            return file_path.read_text(
                encoding="utf-8"
            )

        except UnicodeDecodeError:
            logger.warning(
                "%s was not UTF-8. Trying Latin-1.",
                file_path.name,
            )

            return file_path.read_text(
                encoding="latin-1"
            )

    def _read_pdf_file(self, file_path: Path,) -> str:
        """
        Extract readable text from a PDF using PyMuPDF.

        Text blocks are sorted by vertical and horizontal
        position to approximate normal reading order.
        """

        page_texts: list[str] = []

        try:
            document = pymupdf.open(file_path)
        except Exception as error:
            raise ValueError(
                f"Could not open PDF: {file_path.name}"
            ) from error

        try:
            if document.needs_pass:
                raise ValueError(
                    f"PDF is password-protected: "
                    f"{file_path.name}"
                )

            for page_number, page in enumerate(
                document,
                start=1,
            ):
                try:
                    page_text = self._extract_page_text(
                        page
                    )

                except Exception:
                    logger.warning(
                        "Could not extract page %d from %s.",
                        page_number,
                        file_path.name,
                        exc_info=True,
                    )
                    continue

                if page_text:
                    page_texts.append(page_text)

        finally:
            document.close()

        return "\n\n".join(page_texts)

    def _extract_page_text(self, page: pymupdf.Page,) -> str:
        """
        Extract text from one PDF page while using
        block coordinates to approximate reading order.
        """

        page_dictionary = page.get_text(
            "dict",
            sort=True,
        )

        text_blocks = []

        for block in page_dictionary.get(
            "blocks",
            [],
        ):
            # Type 0 is a text block.
            if block.get("type") != 0:
                continue

            block_lines = []

            for line in block.get("lines", []):
                span_texts = []

                for span in line.get("spans", []):
                    text = span.get(
                        "text",
                        "",
                    )

                    if text:
                        span_texts.append(text)

                line_text = "".join(
                    span_texts
                ).strip()

                if line_text:
                    block_lines.append(line_text)

            block_text = "\n".join(
                block_lines
            ).strip()

            if block_text:
                bbox = block.get(
                    "bbox",
                    (0.0, 0.0, 0.0, 0.0),
                )

                text_blocks.append(
                    {
                        "text": block_text,
                        "x0": float(bbox[0]),
                        "y0": float(bbox[1]),
                    }
                )

        text_blocks.sort(
            key=lambda item: (
                item["y0"],
                item["x0"],
            )
        )

        return "\n\n".join(
            block["text"]
            for block in text_blocks
        )

    def clean_text(self, text: str,) -> str:
        """
        Remove unnecessary whitespace while preserving
        ordinary paragraph breaks.
        """

        if not isinstance(text, str):
            return ""

        text = text.replace("\r\n", "\n",)

        text = text.replace("\r", "\n",)

        text = text.replace("\t", " ",)

        cleaned_lines = []

        for line in text.split("\n"):
            cleaned_line = re.sub(
                r"[ ]+",
                " ",
                line,
            ).strip()

            cleaned_lines.append(
                cleaned_line
            )

        text = "\n".join(
            cleaned_lines
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )
        return text.strip()

    def split_text(self, text: str,) -> list[str]:
        """
        Split text into overlapping chunks.

        The method attempts to end each chunk at a
        paragraph, sentence, punctuation mark, or space.
        """

        cleaned_text = self.clean_text(text)

        if not cleaned_text:
            return []

        if len(cleaned_text) <= self.chunk_size:
            return [cleaned_text]

        chunks: list[str] = []
        text_length = len(cleaned_text)
        start = 0

        while start < text_length:
            ideal_end = min(
                start + self.chunk_size,
                text_length,
            )

            end = self._find_chunk_end(
                text=cleaned_text,
                start=start,
                ideal_end=ideal_end,
            )

            chunk = cleaned_text[
                start:end
            ].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            proposed_start = (
                end - self.chunk_overlap
            )

            if proposed_start <= start:
                proposed_start = end

            start = self._find_chunk_start(
                text=cleaned_text,
                proposed_start=proposed_start,
                previous_start=start,
            )
        return chunks

    def _find_chunk_end(self, text: str, start: int, ideal_end: int,) -> int:
        """
        Find a natural ending near the intended
        chunk boundary.
        """

        if ideal_end >= len(text):
            return len(text)

        minimum_end = start + (
            self.chunk_size // 2
        )

        search_area = text[
            minimum_end:ideal_end
        ]

        separators = [
            "\n\n",
            ". ",
            "? ",
            "! ",
            "; ",
            ", ",
            " ",
        ]

        for separator in separators:
            position = search_area.rfind(
                separator
            )

            if position != -1:
                return (
                    minimum_end
                    + position
                    + len(separator)
                )

        return ideal_end
    
    def _find_chunk_start(self, text: str, proposed_start: int, previous_start: int,) -> int:
        """
        Move a proposed chunk starting position to the
        beginning of a complete word.

        This prevents chunks from beginning with partial
        words such as "ly" or "ste time".
        """

        if proposed_start <= 0:
            return 0

        if proposed_start >= len(text):
            return len(text)

        start = proposed_start

        # If the proposed position is inside a word, move backward until the beginning of that word.
        while (
            start > previous_start
            and start > 0
            and not text[start - 1].isspace()
        ):
            start -= 1

        # Prevent the algorithm from returning the same starting position and becoming stuck.
        if start <= previous_start:
            start = proposed_start

            # Move forward to the end of the partial word.
            while (
                start < len(text)
                and not text[start].isspace()
            ):
                start += 1

        # Skip whitespace before the actual text.
        while (
            start < len(text)
            and text[start].isspace()
        ):
            start += 1
        return start

    def create_chunks(self, note: dict[str, Any],) -> list[dict[str, Any]]:
        """
        Convert one loaded note into searchable chunks.
        """

        if not isinstance(note, dict):
            logger.warning(
                "Invalid note data was provided."
            )
            return []

        text = note.get(
            "text",
            "",
        )

        if not isinstance(text, str):
            return []

        source = note.get(
            "source",
            "unknown",
        )

        file_type = note.get(
            "file_type",
            "",
        )

        path = note.get("path")

        chunk_texts = self.split_text(text)
        chunks: list[dict[str, Any]] = []

        for chunk_id, chunk_text in enumerate(
            chunk_texts
        ):
            chunks.append(
                {
                    "text": chunk_text,
                    "source": source,
                    "path": path,
                    "file_type": file_type,
                    "chunk_id": chunk_id,
                }
            )

        logger.info(
            "Created %d chunk(s) from %s.",
            len(chunks),
            source,
        )
        return chunks

    def create_all_chunks(self,) -> list[dict[str, Any]]:
        """
        Load every note and return all chunks.
        """

        notes = self.load_all_notes()

        if not notes:
            return []

        all_chunks: list[
            dict[str, Any]
        ] = []

        for note in notes:
            all_chunks.extend(
                self.create_chunks(note)
            )

        logger.info(
            "Created %d total note chunk(s).",
            len(all_chunks),
        )
        return all_chunks