from datetime import datetime
from pathlib import Path
import logging
import whisper
from config import (
    TRANSCRIPT_DIR,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WHISPER_TASK,
)

logger = logging.getLogger(__name__)

class Transcriber:
    """
    Handles speech-to-text transcription using OpenAI Whisper.
    """

    def __init__(self):
        logger.info("Loading Whisper model (model=%s).", WHISPER_MODEL)
        try:
            self.model = whisper.load_model(WHISPER_MODEL)
        except Exception as error:
            logger.exception("Whisper model loading failed.")
            raise RuntimeError("The Whisper model could not be loaded.") from error
        logger.info("Whisper model loaded successfully.")

    def transcribe(self, audio_path: Path | str) -> tuple[str, Path]:
        """
        Transcribe an audio file and save the resulting text.
        """

        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file does not exist: {audio_path}"
            )

        if not audio_path.is_file():
            raise ValueError(
                f"Audio path is not a file: {audio_path}"
            )

        transcription_options = {
            "task": WHISPER_TASK,
        }

        if WHISPER_LANGUAGE is not None:
            transcription_options["language"] = WHISPER_LANGUAGE

        logger.info(
            "Starting transcription (audio_file=%s, language=%s, task=%s).",
            audio_path.name,
            WHISPER_LANGUAGE or "automatic",
            WHISPER_TASK,
        )

        try:
            result = self.model.transcribe(
                str(audio_path),
                **transcription_options,
            )
        except Exception as error:
            logger.exception("Whisper transcription failed (audio_file=%s).", audio_path.name)
            raise RuntimeError("Whisper could not transcribe the selected audio file.") from error

        transcript = result["text"].strip()

        if not transcript:
            raise ValueError(
                "Whisper did not produce any transcript text."
            )
    
        transcript_path = self._save_transcript(transcript)
        logger.info(
            "Transcription saved successfully (chars=%d, output_file=%s).",
            len(transcript),
            transcript_path.name,
        )
        return transcript, transcript_path

    def _save_transcript(self, transcript: str) -> Path:
        """Save transcript text and return its file path."""

        filename = (
            f"transcript_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )

        filepath = TRANSCRIPT_DIR / filename

        try:
            filepath.write_text(transcript, encoding="utf-8")
        except OSError as error:
            logger.exception("Transcript file could not be saved (file=%s).", filepath.name)
            raise RuntimeError("The transcript could not be saved.") from error
        return filepath