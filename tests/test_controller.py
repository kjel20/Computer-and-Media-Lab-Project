from pathlib import Path
import pytest
from src.controller import LectureController

class FakeRecorder:
    def __init__(self, output_path: Path) -> None:
        self.recording = False
        self.output_path = output_path

    def start_recording(self) -> None:
        self.recording = True

    def stop_recording(self) -> None:
        self.recording = False

    def save_recording(self) -> Path:
        return self.output_path

class FakeTranscriber:
    def __init__(
        self,
        transcript_path: Path,
    ) -> None:
        self.transcript_path = transcript_path

    def transcribe(
        self,
        audio_path: Path,
    ) -> tuple[str, Path]:
        return (
            "Test transcript",
            self.transcript_path,
        )

class FakeNoteGenerationService:
    def generate_notes(self, **kwargs) -> dict:
        return {
            "structured_notes": {
                "title": "Test Notes",
            },
            "document_path": Path(
                "test_notes.docx"
            ),
        }

    def check_prerequisites(self) -> dict:
        return {
            "ready": True,
        }

    def clear_retriever_index(self) -> None:
        pass

def create_controller(
    tmp_path: Path,
) -> LectureController:
    return LectureController(
        recorder=FakeRecorder(
            tmp_path / "recording.wav"
        ),
        transcriber=FakeTranscriber(
            tmp_path / "transcript.txt"
        ),
        note_generation_service=(
            FakeNoteGenerationService()
        ),
    )

def test_validate_audio_accepts_existing_wav(
    tmp_path: Path,
) -> None:
    controller = create_controller(tmp_path)

    audio_path = tmp_path / "lecture.wav"
    audio_path.write_bytes(b"audio")

    result = controller.validate_audio_file(
        audio_path
    )
    assert result == audio_path

def test_validate_audio_rejects_unsupported_extension(
    tmp_path: Path,
) -> None:
    controller = create_controller(tmp_path)

    audio_path = tmp_path / "lecture.txt"
    audio_path.write_text(
        "not audio",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported audio format",
    ):
        controller.validate_audio_file(
            audio_path
        )

def test_save_transcript_changes_writes_clean_text(
    tmp_path: Path,
) -> None:
    controller = create_controller(tmp_path)
    transcript_path = tmp_path / "edited.txt"

    saved_path = (
        controller.save_transcript_changes(
            transcript=(
                "  Corrected transcript.  "
            ),
            transcript_path=transcript_path,
        )
    )
    assert saved_path == transcript_path

    assert transcript_path.read_text(
        encoding="utf-8"
    ) == "Corrected transcript."

def test_empty_transcript_is_rejected(
    tmp_path: Path,
) -> None:
    controller = create_controller(tmp_path)

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        controller.generate_formatted_notes(
            edited_transcript="   "
        )

def test_generation_is_delegated_to_service(
    tmp_path: Path,
) -> None:
    controller = create_controller(tmp_path)

    result = controller.generate_formatted_notes(
        edited_transcript=(
            "A valid lecture transcript."
        ),
        filename="test_notes",
    )

    assert (
        result["structured_notes"]["title"]
        == "Test Notes"
    )