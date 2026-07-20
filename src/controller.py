from pathlib import Path
from typing import Optional
from src.recorder import Recorder
from src.transcriber import Transcriber


class LectureController:
    """
    Coordinates audio recording and transcription.

    The Streamlit interface communicates with this controller
    instead of using Recorder and Transcriber directly.
    """

    def __init__(self):
        self.recorder = Recorder()
        self.transcriber = Transcriber()
        self.latest_audio_path: Optional[Path] = None
        self.latest_transcript: Optional[str] = None
        self.latest_transcript_path: Optional[Path] = None

    def start_recording(self) -> None:
        if self.recorder.recording:
            raise RuntimeError("A recording is already in progress.")
        self.recorder.start_recording()

    def stop_recording(self) -> Path:
        """
        Returns
        -------
        Path
            The location of the saved WAV file.
        """

        if not self.recorder.recording:
            raise RuntimeError("No recording is currently in progress.")
        self.recorder.stop_recording()
        self.latest_audio_path = self.recorder.save_recording()

        return self.latest_audio_path

    def set_audio_file(self, audio_path: Path | str) -> Path:
        """
        Select an existing audio file for transcription.

        This will later allow the Streamlit app to support
        uploaded lecture recordings.
        """

        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file does not exist: {path}"
            )

        if path.suffix.lower() not in {
            ".wav",
            ".mp3",
            ".m4a",
            ".flac",
            ".ogg",
        }:
            raise ValueError(
                f"Unsupported audio format: {path.suffix}"
            )

        self.latest_audio_path = path

        return path

    def transcribe_latest(self) -> tuple[str, Path]:
        """
        Transcribe the currently selected or most recently recorded audio.

        Returns
        -------
        tuple[str, Path]
            The transcript text and saved transcript path.
        """

        if self.latest_audio_path is None:
            raise ValueError(
                "No audio file is available. Record or upload audio first."
            )

        transcript, transcript_path = self.transcriber.transcribe(
            self.latest_audio_path
        )

        self.latest_transcript = transcript
        self.latest_transcript_path = transcript_path

        return transcript, transcript_path

    def is_recording(self) -> bool:
        """Return whether the microphone is currently recording."""

        return self.recorder.recording