from pathlib import Path

# --------------------------------------------------
# Base project directory
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------
# Main directories
# --------------------------------------------------

DATA_DIR = BASE_DIR / "data"

AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
NOTES_DIR = DATA_DIR / "notes"

STYLE_PROFILES_DIR = DATA_DIR / "style_profiles"
GENERATED_DOCUMENTS_DIR = DATA_DIR / "generated_documents"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "ai_lecture_companion.log"

# --------------------------------------------------
# Create required directories automatically
# --------------------------------------------------

REQUIRED_DIRECTORIES = [
    DATA_DIR,
    AUDIO_DIR,
    TRANSCRIPT_DIR,
    NOTES_DIR,
    STYLE_PROFILES_DIR,
    GENERATED_DOCUMENTS_DIR,
    LOG_DIR,
]

for directory in REQUIRED_DIRECTORIES:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# --------------------------------------------------
# Logging settings
# --------------------------------------------------

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3

# --------------------------------------------------
# Audio recording settings
# --------------------------------------------------

AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 1
AUDIO_DTYPE = "int16"

# --------------------------------------------------
# Whisper transcription settings
# --------------------------------------------------

WHISPER_MODEL = "small"
WHISPER_LANGUAGE = "en"
WHISPER_TASK = "transcribe"

# --------------------------------------------------
# Ollama settings
# --------------------------------------------------

OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_HOST = "http://localhost:11434"

OLLAMA_TEMPERATURE = 0.3
OLLAMA_NUM_PREDICT = 2000

# Maximum time allowed for one Ollama request.
# Local generation can be slow on CPU-only computers.
OLLAMA_TIMEOUT_SECONDS = 300

# --------------------------------------------------
# Embedding model settings
# --------------------------------------------------

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --------------------------------------------------
# Supported file types
# --------------------------------------------------

SUPPORTED_NOTE_EXTENSIONS = {
    ".txt",
    ".pdf",
}

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
}

# --------------------------------------------------
# Note chunking settings
# --------------------------------------------------

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# --------------------------------------------------
# Retrieval settings
# --------------------------------------------------

TOP_K_RESULTS = 4
MIN_SIMILARITY_SCORE = 0.20

# --------------------------------------------------
# Style-extraction settings
# --------------------------------------------------

# Ignore spans that contain only whitespace.
IGNORE_EMPTY_STYLE_SPANS = True

# Round extracted measurements so that tiny PDF coordinate differences do not create separate styles.
STYLE_FONT_SIZE_DECIMALS = 1
STYLE_POSITION_DECIMALS = 1
STYLE_SPACING_DECIMALS = 1

# Spacing larger than this value is still recorded, but may later be treated as a section or page-layout gap.
MAX_NORMAL_PARAGRAPH_GAP = 72.0

# A small tolerance used when comparing indentation.
INDENT_TOLERANCE = 3.0

# --------------------------------------------------
# Style-profile settings
# --------------------------------------------------

STYLE_PROFILE_FILENAME = "detected_style_profile.json"

DEFAULT_FALLBACK_FONT = "Arial"
DEFAULT_BODY_FONT = "Arial"

DEFAULT_BODY_FONT_SIZE = 11.0
DEFAULT_TITLE_SIZE = 20.0
DEFAULT_HEADING_1_SIZE = 16.0
DEFAULT_HEADING_2_SIZE = 14.0
DEFAULT_HEADING_3_SIZE = 12.0

# --------------------------------------------------
# Resolved style-profile settings
# --------------------------------------------------

STYLE_OVERRIDE_FILENAME = "style_overrides.json"
RESOLVED_STYLE_PROFILE_FILENAME = "resolved_style_profile.json"

# Safe fallback values used when detected values are missing, invalid, or unrealistic.
STYLE_FALLBACKS = {
    "page": {
        "width": 595.3,
        "height": 841.9,
        "margin_left": 72.0,
        "margin_right": 72.0,
        "margin_top": 72.0,
        "margin_bottom": 72.0,
    },
    "body": {
        "font": "Arial",
        "font_size": 11.0,
        "bold": False,
        "italic": False,
        "color": "#000000",
        "line_spacing_points": 14.6,
        "line_spacing_ratio": 1.33,
        "paragraph_spacing_before": 0.0,
        "paragraph_spacing_after": 12.0,
    },
    "title": {
        "font": "Arial",
        "font_size": 18.0,
        "bold": True,
        "italic": False,
        "color": "#000000",
        "alignment": "left",
        "spacing_after": 12.0,
    },
    "heading_1": {
        "font": "Arial",
        "font_size": 16.0,
        "bold": True,
        "italic": False,
        "color": "#000000",
        "spacing_before": 12.0,
        "spacing_after": 6.0,
    },
    "heading_2": {
        "font": "Arial",
        "font_size": 13.0,
        "bold": True,
        "italic": False,
        "color": "#000000",
        "spacing_before": 10.0,
        "spacing_after": 5.0,
    },
    "heading_3": {
        "font": "Arial",
        "font_size": 11.0,
        "bold": True,
        "italic": False,
        "color": "#000000",
        "spacing_before": 8.0,
        "spacing_after": 4.0,
    },
    "bullet": {
        "font": "Arial",
        "font_size": 11.0,
        "color": "#000000",
        "indent_left": 36.0,
        "hanging_indent": 12.6,
        "nested_indent_increment": 36.0,
        "spacing_after": 3.0,
    },
}

# Manual corrections applied after automatic detection. Use an empty dictionary when no correction is needed.
DEFAULT_STYLE_OVERRIDES = {
    "title": {
        "font_size": 16.0,
        "bold": False,
    },
    "heading_1": {
        "font_size": 16.0,
        "bold": False,
    },
    "heading_2": {
        "font_size": 11.0,
        "bold": True,
    },
    "heading_3": {
        "font_size": 11.0,
        "bold": True,
    },
    "page": {
        "margin_bottom": 72.0,
    },
    "bullet": {
        "indent_left": 18.0,
        "hanging_indent": 10.0,
        "nested_indent_increment": 18.0,
        "spacing_after": 1.5,
    },
    "body": {
        "paragraph_spacing_before": 0.0,
        "paragraph_spacing_after": 5.0,
        "line_spacing_points": 13.0,
        "line_spacing_ratio": 1.15,
    },
}

# --------------------------------------------------
# Output filename settings
# --------------------------------------------------

GENERATED_DOCUMENT_FILE_PREFIX = "formatted_lecture_notes"

# --------------------------------------------------
# DOCX renderer settings
# --------------------------------------------------

DOCX_FILE_EXTENSION = ".docx"

# Font used when the detected PDF font cannot be used.
DOCX_FALLBACK_FONT = DEFAULT_FALLBACK_FONT

# Word-compatible style names that the renderer will configure.
DOCX_NORMAL_STYLE_NAME = "Normal"
DOCX_TITLE_STYLE_NAME = "Title"
DOCX_SUBTITLE_STYLE_NAME = "Subtitle"
DOCX_HEADING_1_STYLE_NAME = "Heading 1"
DOCX_HEADING_2_STYLE_NAME = "Heading 2"
DOCX_HEADING_3_STYLE_NAME = "Heading 3"

# Labels used for special generated-note sections.
DOCX_SUMMARY_HEADING = "Summary"
DOCX_EXAMPLES_HEADING = ""

# Bullet symbols used by the renderer.
DOCX_BULLET_SYMBOL = "-"
DOCX_NESTED_BULLET_SYMBOL = "-"

# Definitions will appear as:
# Term: definition
DOCX_DEFINITION_SEPARATOR = " "

# Generated documents receive timestamped names.
DOCX_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# Safety limits for values applied to Word documents.
DOCX_MIN_FONT_SIZE = 6.0
DOCX_MAX_FONT_SIZE = 40.0
DOCX_MIN_MARGIN = 0.0
DOCX_MAX_MARGIN = 216.0