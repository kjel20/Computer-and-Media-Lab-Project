import logging
from pathlib import Path
from typing import Any

from config import SUPPORTED_AUDIO_EXTENSIONS
from src.note_generation_service import NoteGenerationService
from src.progress import ProgressCallback
from src.recorder import Recorder
from src.transcriber import Transcriber

logger = logging.getLogger(__name__)


class LectureController:
    """Coordinate recording, transcription, editing, and formatted-note generation."""

    def __init__(self, recorder: Recorder | None = None, transcriber: Transcriber | None = None,
                 note_generation_service: NoteGenerationService | None = None) -> None:
        self.recorder = recorder or Recorder()
        self.transcriber = transcriber or Transcriber()
        self.note_generation_service = note_generation_service or NoteGenerationService()
        logger.info("Lecture controller initialized.")

    def start_recording(self) -> None:
        logger.info("Recording start requested.")
        self.recorder.start_recording()

    def stop_recording(self) -> Path:
        logger.info("Recording stop requested.")
        self.recorder.stop_recording()
        path = self.recorder.save_recording()
        logger.info("Recording workflow completed (file=%s).", path.name)
        return path

    def validate_audio_file(self, audio_path: Path | str) -> Path:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Audio path is not a file: {path}")
        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
            raise ValueError(
                f"Unsupported audio format: {path.suffix or 'none'}. Supported formats are: {supported}"
            )
        logger.info("Audio file validated (extension=%s, bytes=%d).", path.suffix.lower(), path.stat().st_size)
        return path

    def transcribe(self, audio_path: Path | str) -> tuple[str, Path]:
        validated_path = self.validate_audio_file(audio_path)
        logger.info("Transcription requested (audio_file=%s).", validated_path.name)
        transcript, transcript_path = self.transcriber.transcribe(validated_path)
        logger.info("Transcription completed (chars=%d, output_file=%s).", len(transcript), transcript_path.name)
        return transcript, transcript_path

    def save_transcript_changes(self, transcript: str, transcript_path: Path | str) -> Path:
        if not isinstance(transcript, str):
            raise TypeError("Edited transcript must be a string.")
        transcript = transcript.strip()
        if not transcript:
            raise ValueError("Edited transcript cannot be empty.")
        path = Path(transcript_path)
        if path.suffix.lower() != ".txt":
            raise ValueError("Transcript changes can only be saved to a .txt file.")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(transcript, encoding="utf-8")
        except OSError as error:
            logger.exception("Edited transcript could not be saved (file=%s).", path.name)
            raise RuntimeError(f"The edited transcript could not be saved: {path}") from error
        logger.info("Edited transcript saved (chars=%d, file=%s).", len(transcript), path.name)
        return path

    def generate_formatted_notes(self, edited_transcript: str, filename: str | None = None,
                                 top_k: int | None = None, min_similarity_score: float | None = None,
                                 progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
        transcript = self._validate_transcript(edited_transcript)
        logger.info("Formatted-note generation requested (transcript_chars=%d).", len(transcript))
        return self.note_generation_service.generate_notes(
            edited_transcript=transcript,
            filename=filename,
            top_k=top_k,
            min_similarity_score=min_similarity_score,
            progress_callback=progress_callback,
        )

    def check_note_generation_prerequisites(self) -> dict[str, Any]:
        return self.note_generation_service.check_prerequisites()

    def clear_note_retrieval_index(self) -> None:
        self.note_generation_service.clear_retriever_index()

    def is_recording(self) -> bool:
        return self.recorder.recording

    def _validate_transcript(self, transcript: str) -> str:
        if not isinstance(transcript, str):
            raise TypeError("Edited transcript must be a string.")
        transcript = transcript.strip()
        if not transcript:
            raise ValueError("Edited transcript cannot be empty.")
        return transcript
