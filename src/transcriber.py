from datetime import datetime
from pathlib import Path
import whisper
from config import TRANSCRIPT_DIR

class Transcriber:
    """
    Handles speech-to-text transcription using OpenAI Whisper.
    """

    def __init__(self):
        print("Loading Whisper model...")

        # Load once when the application starts
        self.model = whisper.load_model("small")

        print("Whisper model loaded successfully.")

    def transcribe(self, audio_path: Path) -> tuple[str, Path]:
        """
        Parameters
        ----------
        audio_path : Path
            Path to the WAV file.

        Returns
        -------
        tuple
            (transcript_text, transcript_file_path)
        """

        result = self.model.transcribe(str(audio_path),language="en",task="transcribe")
        transcript = result["text"].strip()
        transcript_path = self._save_transcript(transcript)

        return transcript, transcript_path

    def _save_transcript(self, transcript: str) -> Path:
        """
        Returns
        -------
        Path
            Path of the saved transcript.
        """

        filename = (
            f"transcript_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )

        filepath = TRANSCRIPT_DIR / filename

        filepath.write_text(
            transcript,
            encoding="utf-8",
        )
        return filepath