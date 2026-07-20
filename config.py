from pathlib import Path

# Project folders

PROJECT_ROOT = Path(__file__).parent

DATA_DIR = PROJECT_ROOT / "data"

AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
NOTES_DIR = DATA_DIR / "notes"
GENERATED_DIR = DATA_DIR / "generated_notes"

# Create folders automatically

for folder in [
    AUDIO_DIR,
    TRANSCRIPT_DIR,
    NOTES_DIR,
    GENERATED_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)