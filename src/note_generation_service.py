import json
import logging
from pathlib import Path
from typing import Any

from config import MIN_SIMILARITY_SCORE, RESOLVED_STYLE_PROFILE_FILENAME, STYLE_PROFILES_DIR, TOP_K_RESULTS
from src.docx_renderer import DocxRenderer
from src.generator import NoteGenerator
from src.note_library import NoteLibrary
from src.progress import ProgressCallback, report_progress
from src.prompt_builder import PromptBuilder
from src.retriever import Retriever

logger = logging.getLogger(__name__)


class NoteGenerationService:
    """Coordinate retrieval, AI generation, validation, and DOCX rendering."""

    def __init__(self, note_library: NoteLibrary | None = None, retriever: Retriever | None = None,
                 prompt_builder: PromptBuilder | None = None, generator: NoteGenerator | None = None,
                 renderer: DocxRenderer | None = None, style_profile_path: Path | None = None) -> None:
        self.note_library = note_library or NoteLibrary()
        self.retriever = retriever or Retriever()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.generator = generator or NoteGenerator()
        self.renderer = renderer or DocxRenderer()
        self.style_profile_path = Path(
            style_profile_path or STYLE_PROFILES_DIR / RESOLVED_STYLE_PROFILE_FILENAME
        )

    def generate_notes(self, edited_transcript: str, filename: str | None = None,
                       top_k: int | None = None, min_similarity_score: float | None = None,
                       progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
        """Run the full pipeline and return notes, document, retrieval, and style metadata."""
        transcript = self._validate_transcript(edited_transcript)
        result_limit = TOP_K_RESULTS if top_k is None else top_k
        score_threshold = MIN_SIMILARITY_SCORE if min_similarity_score is None else min_similarity_score
        self._validate_retrieval_settings(result_limit, score_threshold)

        logger.info(
            "Starting note-generation pipeline (transcript_chars=%d, top_k=%d, threshold=%.2f).",
            len(transcript), result_limit, score_threshold,
        )
        report_progress(progress_callback, 5, "Validating generation inputs")

        style_profile = self.load_resolved_style_profile()
        report_progress(progress_callback, 15, "Loading the resolved style profile")

        chunks = self.load_note_chunks()
        report_progress(progress_callback, 30, f"Loaded {len(chunks)} reference-note chunks")

        retrieval_results = self.retrieve_reference_examples(
            transcript, chunks, result_limit, score_threshold
        )
        report_progress(
            progress_callback, 50,
            f"Retrieved {len(retrieval_results)} organization and style examples",
        )

        prompt = self.prompt_builder.build_prompt(
            edited_transcript=transcript,
            retrieved_chunks=retrieval_results,
            resolved_style_profile=style_profile,
        )
        logger.info("Prompt prepared (chars=%d, retrieved_examples=%d).", len(prompt), len(retrieval_results))
        report_progress(progress_callback, 60, "Building the structured note-generation prompt")

        report_progress(progress_callback, 68, "Generating structured notes with the local model")
        structured_notes, quality_result = self.generator.generate_quality_checked(
            prompt=prompt,
            transcript=transcript,
            progress_callback=progress_callback,
        )
        report_progress(
            progress_callback, 88,
            f"Content-quality validation completed (score {quality_result.get('score', 'unknown')})",
        )

        document_path = self.renderer.render(
            notes=structured_notes,
            style_profile=style_profile,
            filename=filename,
        )
        report_progress(progress_callback, 97, "Creating the formatted Word document")

        sources_used = self._get_sources_used(retrieval_results)
        result = {
            "structured_notes": structured_notes,
            "document_path": document_path,
            "sources_used": sources_used,
            "retrieval_results": retrieval_results,
            "quality": quality_result,
            "style_profile": style_profile,
            "style_profile_path": self.style_profile_path,
            "indexed_chunk_count": len(chunks),
            "retrieved_chunk_count": len(retrieval_results),
        }

        logger.info(
            "Note-generation pipeline completed (sources=%d, indexed_chunks=%d, retrieved_chunks=%d, quality=%s).",
            len(sources_used), len(chunks), len(retrieval_results), quality_result.get("score", "unknown"),
        )
        report_progress(progress_callback, 100, "Formatted notes generated successfully")
        return result

    def load_note_chunks(self) -> list[dict[str, Any]]:
        logger.info("Loading and chunking reference-note files.")
        try:
            chunks = self.note_library.create_all_chunks()
        except Exception as error:
            logger.exception("Reference-note loading or chunking failed.")
            raise RuntimeError(
                "The reference notes could not be loaded. Check data/notes/ and try again."
            ) from error
        if not isinstance(chunks, list):
            raise RuntimeError("NoteLibrary returned an unexpected chunk result.")
        if not chunks:
            raise ValueError(
                "No usable reference-note chunks were found. Add at least one PDF or TXT file to data/notes/."
            )
        logger.info("Reference-note chunking completed (chunks=%d).", len(chunks))
        return chunks

    def retrieve_reference_examples(self, transcript: str, chunks: list[dict[str, Any]],
                                    top_k: int = TOP_K_RESULTS,
                                    min_similarity_score: float = MIN_SIMILARITY_SCORE) -> list[dict[str, Any]]:
        transcript = self._validate_transcript(transcript)
        if not isinstance(chunks, list):
            raise TypeError("Reference-note chunks must be provided as a list.")
        self._validate_retrieval_settings(top_k, min_similarity_score)

        logger.info("Indexing reference-note chunks (count=%d).", len(chunks))
        indexed_count = self.retriever.index_chunks(chunks)
        if indexed_count == 0:
            raise ValueError("No usable reference-note chunks could be indexed.")

        retrieval_results = self.retriever.retrieve(
            transcript=transcript,
            top_k=top_k,
            min_similarity_score=min_similarity_score,
        )
        if not retrieval_results:
            logger.warning("No reference chunks met the similarity threshold; generation will continue without them.")
        return retrieval_results

    def load_resolved_style_profile(self) -> dict[str, Any]:
        path = self.style_profile_path
        if not path.exists():
            raise FileNotFoundError(
                f"The resolved style profile was not found: {path}. Run style extraction and resolution first."
            )
        if not path.is_file():
            raise ValueError(f"The resolved style-profile path is not a file: {path}")
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"The resolved style profile contains invalid JSON: {path}") from error
        except OSError as error:
            raise RuntimeError(f"The resolved style profile could not be read: {path}") from error
        if not isinstance(profile, dict):
            raise ValueError("The resolved style profile must contain a JSON object.")

        required = ("page", "body", "title", "heading_1", "heading_2", "heading_3", "bullet")
        missing = [name for name in required if not isinstance(profile.get(name), dict)]
        if missing:
            raise ValueError("The resolved style profile is missing required sections: " + ", ".join(missing))
        logger.info("Resolved style profile loaded successfully.")
        return profile

    def check_prerequisites(self) -> dict[str, Any]:
        profile_exists = self.style_profile_path.exists() and self.style_profile_path.is_file()
        try:
            note_files = self.note_library.get_note_files()
        except Exception:
            logger.exception("Could not inspect reference-note files during prerequisite check.")
            note_files = []

        ollama_running = self.generator.check_connection()
        model_available = False
        if ollama_running:
            try:
                model_available = self.generator.check_model_available()
            except Exception:
                logger.exception("Could not verify the configured Ollama model.")

        result = {
            "ready": all((profile_exists, bool(note_files), ollama_running, model_available)),
            "style_profile_exists": profile_exists,
            "reference_note_count": len(note_files),
            "reference_note_files": [path.name for path in note_files],
            "ollama_running": ollama_running,
            "model_available": model_available,
        }
        logger.info(
            "Prerequisite check completed (ready=%s, notes=%d, profile=%s, ollama=%s, model=%s).",
            result["ready"], len(note_files), profile_exists, ollama_running, model_available,
        )
        return result

    def clear_retriever_index(self) -> None:
        self.retriever.clear_index()
        logger.info("In-memory retrieval index cleared.")

    def _get_sources_used(self, retrieval_results: list[dict[str, Any]]) -> list[str]:
        sources = {
            str(result.get("source", "")).strip()
            for result in retrieval_results
            if isinstance(result, dict) and str(result.get("source", "")).strip()
        }
        return sorted(sources)

    def _validate_transcript(self, transcript: str) -> str:
        if not isinstance(transcript, str):
            raise TypeError("The edited transcript must be a string.")
        transcript = transcript.strip()
        if not transcript:
            raise ValueError("The edited transcript cannot be empty.")
        return transcript

    def _validate_retrieval_settings(self, top_k: int, min_similarity_score: float) -> None:
        if not isinstance(top_k, int):
            raise TypeError("top_k must be an integer.")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        if not isinstance(min_similarity_score, (int, float)):
            raise TypeError("Minimum similarity score must be numeric.")
        if not -1.0 <= min_similarity_score <= 1.0:
            raise ValueError("Minimum similarity score must be between -1.0 and 1.0.")
