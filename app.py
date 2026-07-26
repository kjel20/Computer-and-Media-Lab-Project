from datetime import datetime
from pathlib import Path
import json
import streamlit as st
from config import (
    AUDIO_DIR,
    NOTES_DIR,
    RESOLVED_STYLE_PROFILE_FILENAME,
    STYLE_OVERRIDE_FILENAME,
    STYLE_PROFILES_DIR,
)
import logging
from src.controller import LectureController
from src.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Page configuration

st.set_page_config(
    page_title="AI Lecture Companion",
    page_icon="🎓",
    layout="wide",
)

# Session state

if "controller" not in st.session_state:
    with st.spinner("Loading Whisper and retrieval models..."):
        st.session_state.controller = LectureController()

if "transcript" not in st.session_state:
    st.session_state.transcript = ""

if "audio_path" not in st.session_state:
    st.session_state.audio_path = None

if "transcript_path" not in st.session_state:
    st.session_state.transcript_path = None

if "generated_notes" not in st.session_state:
    st.session_state.generated_notes = None

if "generated_document_path" not in st.session_state:
    st.session_state.generated_document_path = None

if "generation_sources" not in st.session_state:
    st.session_state.generation_sources = []

if "retrieval_results" not in st.session_state:
    st.session_state.retrieval_results = []

if "generation_quality" not in st.session_state:
    st.session_state.generation_quality = None

if "generation_style_profile" not in st.session_state:
    st.session_state.generation_style_profile = None

controller = st.session_state.controller

# Helper function

def save_uploaded_audio(uploaded_file) -> Path:
    # Save an uploaded audio file inside the project's audio folder.

    safe_filename = Path(uploaded_file.name).name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = AUDIO_DIR / f"uploaded_{timestamp}_{safe_filename}"
    filepath.write_bytes(uploaded_file.getbuffer())
    return filepath

def build_unique_path(directory: Path, original_name: str) -> Path:
    """Return a safe path without overwriting an existing file."""

    safe_name = Path(original_name).name
    destination = directory / safe_name

    if not destination.exists():
        return destination

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = directory / (
        f"{destination.stem}_{timestamp}{destination.suffix}"
    )

    counter = 2

    while candidate.exists():
        candidate = directory / (
            f"{destination.stem}_{timestamp}_{counter}"
            f"{destination.suffix}"
        )
        counter += 1
    return candidate


def save_reference_note(uploaded_file) -> Path:
    """Save one uploaded PDF or TXT reference note safely."""

    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix not in {".pdf", ".txt"}:
        raise ValueError(
            "Only PDF and TXT reference notes are supported."
        )

    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    destination = build_unique_path(
        directory=NOTES_DIR,
        original_name=uploaded_file.name,
    )

    destination.write_bytes(
        uploaded_file.getbuffer()
    )
    return destination


def get_existing_reference_notes() -> list[Path]:
    """Return existing PDF and TXT files from the note library."""

    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    return sorted(
        (
            path
            for path in NOTES_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".pdf", ".txt"}
        ),
        key=lambda path: path.name.lower(),
    )

def load_json_file(path: Path) -> dict:
    """Load one JSON object safely."""

    if not path.exists() or not path.is_file():
        return {}

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}

def save_json_file(path: Path, data: dict) -> Path:
    """Save one dictionary as readable UTF-8 JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path

def deep_merge(base: dict, updates: dict) -> dict:
    """Recursively merge nested dictionaries."""

    merged = base.copy()

    for key, value in updates.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = deep_merge(
                merged[key],
                value,
            )
        else:
            merged[key] = value
    return merged

def get_detected_profile_path() -> Path:
    """Find the existing detected style-profile file."""

    candidates = [
        STYLE_PROFILES_DIR / "detected_style_profile.json",
        STYLE_PROFILES_DIR / "style_profile.json",
        STYLE_PROFILES_DIR / "generated_style_profile.json",
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            return path

    return candidates[0]

def get_style_profile_paths() -> dict[str, Path]:
    """Return all style-profile paths used by the interface."""

    return {
        "detected": get_detected_profile_path(),
        "overrides": STYLE_PROFILES_DIR / STYLE_OVERRIDE_FILENAME,
        "resolved": STYLE_PROFILES_DIR / RESOLVED_STYLE_PROFILE_FILENAME,
    }

def rebuild_resolved_style_profile() -> dict:
    """
    Merge the detected profile with saved manual overrides.

    When the original detected profile is unavailable, the current
    resolved profile is used as the safe base.
    """

    paths = get_style_profile_paths()

    detected = load_json_file(
        paths["detected"]
    )

    current_resolved = load_json_file(
        paths["resolved"]
    )

    overrides = load_json_file(
        paths["overrides"]
    )

    base_profile = detected or current_resolved

    if not base_profile:
        raise FileNotFoundError(
            "No detected or resolved style profile was found. "
            "Run the style-extraction and profile steps first."
        )

    resolved = deep_merge(
        base_profile,
        overrides,
    )

    resolution_info = resolved.get(
        "resolution",
        {},
    )

    if not isinstance(resolution_info, dict):
        resolution_info = {}

    resolution_info["manual_overrides_applied"] = bool(
        overrides
    )

    resolved["resolution"] = resolution_info

    save_json_file(
        paths["resolved"],
        resolved,
    )
    return resolved

def profile_value(profile: dict, section: str, key: str, fallback,):
    """Read a nested profile value safely."""

    section_data = profile.get(
        section,
        {},
    )

    if not isinstance(section_data, dict):
        return fallback

    value = section_data.get(
        key,
        fallback,
    )
    return fallback if value is None else value

def clear_generated_note_state() -> None:
    """Clear generated-note results when the lecture input changes."""

    st.session_state.generated_notes = None
    st.session_state.generated_document_path = None
    st.session_state.generation_sources = []
    st.session_state.retrieval_results = []
    st.session_state.generation_quality = None
    st.session_state.generation_style_profile = None

def display_structured_notes(notes: dict) -> None:
    """Display generated structured notes in a readable Streamlit preview."""

    if not isinstance(notes, dict):
        st.warning("The generated note preview is unavailable.")
        return

    title = notes.get("title", "")
    subtitle = notes.get("subtitle", "")
    sections = notes.get("sections", [])
    summary = notes.get("summary", [])

    if title:
        st.markdown(f"## {title}")

    if subtitle:
        st.caption(subtitle)

    for section in sections:
        if not isinstance(section, dict):
            continue

        heading = section.get("heading", "")

        if heading:
            st.markdown(f"### {heading}")

        for paragraph in section.get("paragraphs", []):
            if isinstance(paragraph, str) and paragraph.strip():
                st.write(paragraph)

        for bullet in section.get("bullets", []):
            if not isinstance(bullet, dict):
                continue

            bullet_text = bullet.get("text", "")

            if isinstance(bullet_text, str) and bullet_text.strip():
                st.markdown(f"- {bullet_text}")

            for child in bullet.get("children", []):
                if isinstance(child, str) and child.strip():
                    st.markdown(f"  - {child}")

        definitions = section.get("definitions", [])

        for definition in definitions:
            if not isinstance(definition, dict):
                continue

            term = definition.get("term", "")
            meaning = definition.get("definition", "")

            if (
                isinstance(term, str)
                and term.strip()
                and isinstance(meaning, str)
                and meaning.strip()
            ):
                term_text = term.strip()
                meaning_text = meaning.strip()
                lower_meaning = meaning_text.lower()

                existing_connectors = (
                    "is ", "are ", "means ", "describes ", "refers to ", "represents ", "defines ",
                    "explains ", "shows ", "demonstrates ", "indicates ", "occurs ", "happens ", "works ", "behaves ",
                    "allows ", "enables ", "uses ", "takes ", "accepts ", "returns ", "produces ", "creates ",
                    "generates ", "converts ", "transforms ", "stores ", "contains ", "provides ",
                    "checks ", "tests ", "verifies ", "validates ", "ensures ", "identifies ", "detects ",
                    "determines ", "measures ", "calculates ", "compares ", "evaluates ", "analyzes ",
                    "consists of ", "includes ", "involves ", "connects ", "combines ", "organizes ", "groups ", "separates ",
                    "helps ", "prevents ", "protects ", "controls ", "manages ", "supports ", "improves ",
                    "reduces ", "increases ", "focuses on ", "depends on ",
                )

                if lower_meaning.startswith(existing_connectors):
                    connector = " "
                else:
                    connector = " describes "
                    meaning_text = meaning_text[0].lower() + meaning_text[1:]

                st.markdown(
                    f"**{term_text}**{connector}{meaning_text}"
                )

        examples = section.get("examples", [])

        for example in examples:
            if not isinstance(example, str):
                continue

            example_text = example.strip()

            if not example_text:
                continue

            if example_text.lower().startswith(
                ("for example", "for instance", "e.g.")
            ):
                st.write(example_text)
            else:
                st.write(
                    f"For example, "
                    f"{example_text[0].lower()}"
                    f"{example_text[1:]}"
                )

    if summary:
        st.markdown("### Summary")

        for item in summary:
            if isinstance(item, str) and item.strip():
                st.markdown(f"- {item}")

# Sidebar

with st.sidebar:
    st.header("Lecture Workflow")

    st.markdown(
        """
        1. Record or upload audio  
        2. Transcribe the lecture  
        3. Review the transcript  
        4. Add reference notes  
        5. Review the style profile  
        6. Generate personalized notes
        """
    )

    st.divider()

    st.subheader("System Status")

    if controller.is_recording():
        st.warning("Microphone is recording")
    else:
        st.success("Recorder ready")

    if st.session_state.audio_path:
        st.success("Audio selected")
    else:
        st.info("No audio selected")

    if st.session_state.transcript:
        st.success("Transcript ready")
    else:
        st.info("No transcript generated")

    reference_notes = get_existing_reference_notes()

    if reference_notes:
        st.success(
            f"{len(reference_notes)} reference note file(s)"
        )
    else:
        st.info("No reference notes added")

    style_paths = get_style_profile_paths()

    if style_paths["resolved"].exists():
        st.success("Style profile ready")
    else:
        st.info("No resolved style profile")

# Main page

st.title("AI Lecture Companion")

st.write(
    "Record or upload lecture audio, convert it into a transcript, "
    "and generate personalized notes based on your own writing style."
)

st.divider()

# Audio input section

st.header("1. Add Lecture Audio")

recording_tab, upload_tab = st.tabs(
    ["🎤 Record Audio", "📁 Upload Audio"]
)

# Recording tab

with recording_tab:
    st.subheader("Record using your microphone")

    start_column, stop_column = st.columns(2)

    with start_column:
        if st.button(
            "Start Recording",
            disabled=controller.is_recording(),
            use_container_width=True,
        ):
            try:
                controller.start_recording()
                st.success("Recording started.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not start recording: {error}")

    with stop_column:
        if st.button(
            "Stop and Save Recording",
            disabled=not controller.is_recording(),
            use_container_width=True,
        ):
            try:
                audio_path = controller.stop_recording()

                st.session_state.audio_path = audio_path
                st.session_state.transcript = ""
                st.session_state.transcript_path = None

                # Reset the transcript editor
                st.session_state.pop("transcript_editor", None)
                clear_generated_note_state()

                st.success(
                    f"Recording saved as {audio_path.name}"
                )
                st.rerun()
            except Exception as error:
                st.error(f"Could not stop recording: {error}")

    if controller.is_recording():
        st.warning(
            "Recording is currently active. Speak into your microphone, "
            "then press **Stop and Save Recording**."
        )

# Upload tab

with upload_tab:
    st.subheader("Upload an existing lecture recording")

    uploaded_file = st.file_uploader(
        "Choose an audio file",
        type=["wav", "mp3", "m4a", "flac", "ogg"],
    )

    if uploaded_file is not None:
        st.audio(uploaded_file)

        if st.button(
            "Use Uploaded Audio",
            use_container_width=True,
        ):
            try:
                uploaded_path = save_uploaded_audio(uploaded_file)

                controller.validate_audio_file(uploaded_path)

                st.session_state.audio_path = uploaded_path
                st.session_state.transcript = ""
                st.session_state.transcript_path = None

                # Reset the transcript editor
                st.session_state.pop("transcript_editor", None)
                clear_generated_note_state()

                st.success(
                    f"Selected {uploaded_path.name}"
                )
                st.rerun()
            except Exception as error:
                st.error(f"Could not use uploaded audio: {error}")

# Selected audio

if st.session_state.audio_path:
    st.divider()

    st.subheader("Selected Audio")

    audio_path = Path(st.session_state.audio_path)

    st.write(f"**File:** `{audio_path.name}`")

    if audio_path.exists():
        st.audio(str(audio_path))

# Transcription section

st.divider()

st.header("2. Transcribe Lecture")

if st.button(
    "Transcribe Selected Audio",
    type="primary",
    disabled=st.session_state.audio_path is None,
    use_container_width=True,
):
    try:
        with st.spinner(
            "Whisper is transcribing the lecture. "
            "This may take several minutes..."
        ):
            transcript, transcript_path = controller.transcribe(
                st.session_state.audio_path
            )

        st.session_state.transcript = transcript
        st.session_state.transcript_path = transcript_path
        st.session_state.transcript_editor = transcript
        clear_generated_note_state()

        st.success("Transcription completed.")

    except Exception as error:
        st.error(f"Transcription failed: {error}")

# Transcript section

st.divider()

st.header("3. Review Lecture Transcript")

if st.session_state.transcript:
    edited_transcript = st.text_area(
        "Review and correct the transcript before generating notes",
        value=st.session_state.transcript,
        height=350,
        key="transcript_editor",
    )

    if st.button(
        "Save Transcript Changes",
        use_container_width=True,
    ):
        cleaned_text = edited_transcript.strip()

        if not cleaned_text:
            st.error("The transcript cannot be empty.")

        else:
            st.session_state.transcript = cleaned_text

            if st.session_state.transcript_path:
                saved_path = controller.save_transcript_changes(
                    transcript=cleaned_text,
                    transcript_path=st.session_state.transcript_path,
                )

                st.session_state.transcript_path = saved_path

            st.success("Transcript changes saved.")

    if st.session_state.transcript_path:
        transcript_path = Path(
            st.session_state.transcript_path
        )

        st.caption(f"Saved to: {transcript_path}")

        st.download_button(
            label="Download Transcript",
            data=st.session_state.transcript,
            file_name=transcript_path.name,
            mime="text/plain",
            use_container_width=True,
        )

else:
    st.info(
        "Record or upload lecture audio, then press "
        "**Transcribe Selected Audio**."
    )

# Reference notes section

st.divider()

st.header("4. Reference Notes")

st.write(
    "Upload previous notes that the application can use as examples "
    "of your organization, phrasing, and note-taking style."
)

st.info(
    "**PDF files** provide both written content and visual formatting "
    "information, such as fonts, font sizes, margins, spacing, and "
    "indentation.\n\n"
    "**TXT files** provide written content only. They can help with "
    "organization and phrasing, but they do not contain visual "
    "formatting information."
)

uploaded_reference_notes = st.file_uploader(
    "Choose PDF or TXT reference notes",
    type=["pdf", "txt"],
    accept_multiple_files=True,
    key="reference_note_uploader",
)

if uploaded_reference_notes:

    st.caption(
        f"{len(uploaded_reference_notes)} file(s) selected"
    )

    for uploaded_file in uploaded_reference_notes:
        st.write(f"- `{uploaded_file.name}`")

    if st.button(
        "Save Reference Notes",
        use_container_width=True,
        key="save_reference_notes_button",
    ):

        saved_files = []
        failed_files = []

        with st.spinner("Saving reference notes..."):

            for uploaded_file in uploaded_reference_notes:

                try:
                    saved_path = save_reference_note(
                        uploaded_file
                    )

                    saved_files.append(saved_path)

                except Exception as error:

                    failed_files.append(
                        {
                            "name": uploaded_file.name,
                            "error": str(error),
                        }
                    )

        if saved_files:

            st.success(
                f"Saved {len(saved_files)} reference note file(s)."
            )

            for saved_path in saved_files:
                st.write(f"- `{saved_path.name}`")

            try:
                controller.clear_note_retrieval_index()

            except Exception as error:

                logger.warning(
                    "Could not clear retrieval index: %s",
                    error,
                )

        if failed_files:

            st.error(
                f"{len(failed_files)} file(s) could not be saved."
            )

            for failure in failed_files:

                st.write(
                    f"- `{failure['name']}`: "
                    f"{failure['error']}"
                )

        if saved_files:
            st.rerun()

st.subheader("Existing Reference Notes")

existing_reference_notes = get_existing_reference_notes()

if existing_reference_notes:

    pdf_count = sum(
        note.suffix.lower() == ".pdf"
        for note in existing_reference_notes
    )

    txt_count = sum(
        note.suffix.lower() == ".txt"
        for note in existing_reference_notes
    )

    pdf_column, txt_column, total_column = st.columns(3)

    pdf_column.metric(
        "PDF files",
        pdf_count,
    )

    txt_column.metric(
        "TXT files",
        txt_count,
    )

    total_column.metric(
        "Total files",
        len(existing_reference_notes),
    )

    st.divider()

    for note in existing_reference_notes:

        if note.suffix.lower() == ".pdf":
            description = (
                "Content, organization, and visual formatting"
            )
        else:
            description = (
                "Content and organization only"
            )

        st.write(
            f"**{note.name}**"
        )

        st.caption(
            f"{note.suffix.upper()[1:]} • {description}"
        )

else:

    st.warning(
        "No reference notes are currently available.\n\n"
        "Upload at least one PDF or TXT file before "
        "generating personalized notes."
    )

# Style profile section

st.divider()

st.header("5. Style Profile")

st.write(
    "Review the formatting detected from your PDF reference notes. "
    "You can override the most important values before generating "
    "the final Word document."
)

st.info(
    "Detected values come from the formatting found in your PDFs. "
    "Resolved values are the final settings used by the DOCX renderer "
    "after manual overrides have been applied."
)

style_paths = get_style_profile_paths()

detected_profile = load_json_file(
    style_paths["detected"]
)

resolved_profile = load_json_file(
    style_paths["resolved"]
)

saved_overrides = load_json_file(
    style_paths["overrides"]
)

# Profile status
status_detected, status_resolved, status_overrides = st.columns(3)

status_detected.metric(
    "Detected profile",
    "Ready" if detected_profile else "Missing",
)

status_resolved.metric(
    "Resolved profile",
    "Ready" if resolved_profile else "Missing",
)

status_overrides.metric(
    "Manual overrides",
    "Saved" if saved_overrides else "None",
)

# Display profile values
if detected_profile:
    with st.expander(
        "View Detected Style Values",
        expanded=False,
    ):
        st.json(detected_profile)
else:
    st.warning(
        "The detected style profile could not be found. "
        "The current resolved profile will be used as the editing base."
    )

if resolved_profile:
    with st.expander(
        "View Resolved Style Values",
        expanded=False,
    ):
        st.json(resolved_profile)
else:
    st.warning(
        "No resolved style profile exists yet. "
        "Run the style resolver or rebuild the profile below."
    )

# Choose editing base
editing_profile = (
    resolved_profile
    or detected_profile
)

if editing_profile:
    st.subheader("Formatting Overrides")

    st.caption(
        "Only the values below will be overridden. "
        "All other detected settings will remain unchanged."
    )

    font_column, body_size_column, title_size_column = st.columns(3)

    with font_column:
        body_font = st.text_input(
            "Body font",
            value=str(
                profile_value(
                    editing_profile,
                    "body",
                    "font",
                    "Arial",
                )
            ),
            key="style_body_font",
        )

    with body_size_column:
        body_font_size = st.number_input(
            "Body font size (pt)",
            min_value=6.0,
            max_value=30.0,
            value=float(
                profile_value(
                    editing_profile,
                    "body",
                    "font_size",
                    11.0,
                )
            ),
            step=0.5,
            key="style_body_font_size",
        )

    with title_size_column:
        title_font_size = st.number_input(
            "Title size (pt)",
            min_value=8.0,
            max_value=40.0,
            value=float(
                profile_value(
                    editing_profile,
                    "title",
                    "font_size",
                    18.0,
                )
            ),
            step=0.5,
            key="style_title_font_size",
        )


    heading_1_column, heading_2_column, heading_3_column = st.columns(3)

    with heading_1_column:
        heading_1_size = st.number_input(
            "Heading 1 size (pt)",
            min_value=8.0,
            max_value=36.0,
            value=float(
                profile_value(
                    editing_profile,
                    "heading_1",
                    "font_size",
                    16.0,
                )
            ),
            step=0.5,
            key="style_heading_1_size",
        )

    with heading_2_column:
        heading_2_size = st.number_input(
            "Heading 2 size (pt)",
            min_value=8.0,
            max_value=32.0,
            value=float(
                profile_value(
                    editing_profile,
                    "heading_2",
                    "font_size",
                    13.0,
                )
            ),
            step=0.5,
            key="style_heading_2_size",
        )

    with heading_3_column:
        heading_3_size = st.number_input(
            "Heading 3 size (pt)",
            min_value=6.0,
            max_value=28.0,
            value=float(
                profile_value(
                    editing_profile,
                    "heading_3",
                    "font_size",
                    11.0,
                )
            ),
            step=0.5,
            key="style_heading_3_size",
        )

    st.markdown("#### Page Margins")

    margin_left_column, margin_right_column = st.columns(2)
    margin_top_column, margin_bottom_column = st.columns(2)

    with margin_left_column:
        margin_left = st.number_input(
            "Left margin (pt)",
            min_value=0.0,
            max_value=216.0,
            value=float(
                profile_value(
                    editing_profile,
                    "page",
                    "margin_left",
                    72.0,
                )
            ),
            step=1.0,
            key="style_margin_left",
        )

    with margin_right_column:
        margin_right = st.number_input(
            "Right margin (pt)",
            min_value=0.0,
            max_value=216.0,
            value=float(
                profile_value(
                    editing_profile,
                    "page",
                    "margin_right",
                    72.0,
                )
            ),
            step=1.0,
            key="style_margin_right",
        )

    with margin_top_column:
        margin_top = st.number_input(
            "Top margin (pt)",
            min_value=0.0,
            max_value=216.0,
            value=float(
                profile_value(
                    editing_profile,
                    "page",
                    "margin_top",
                    72.0,
                )
            ),
            step=1.0,
            key="style_margin_top",
        )

    with margin_bottom_column:
        margin_bottom = st.number_input(
            "Bottom margin (pt)",
            min_value=0.0,
            max_value=216.0,
            value=float(
                profile_value(
                    editing_profile,
                    "page",
                    "margin_bottom",
                    72.0,
                )
            ),
            step=1.0,
            key="style_margin_bottom",
        )


    st.markdown("#### Text Spacing")

    line_spacing_column, paragraph_spacing_column = st.columns(2)

    with line_spacing_column:
        line_spacing = st.number_input(
            "Body line spacing (pt)",
            min_value=6.0,
            max_value=40.0,
            value=float(
                profile_value(
                    editing_profile,
                    "body",
                    "line_spacing_points",
                    14.0,
                )
            ),
            step=0.5,
            key="style_line_spacing",
        )

    with paragraph_spacing_column:
        paragraph_spacing = st.number_input(
            "Paragraph spacing after (pt)",
            min_value=0.0,
            max_value=40.0,
            value=float(
                profile_value(
                    editing_profile,
                    "body",
                    "paragraph_spacing_after",
                    6.0,
                )
            ),
            step=0.5,
            key="style_paragraph_spacing",
        )

    st.markdown("#### Bullet Indentation")

    bullet_indent_column, hanging_column, nested_column = st.columns(3)

    with bullet_indent_column:
        bullet_indent = st.number_input(
            "Main bullet indent (pt)",
            min_value=0.0,
            max_value=150.0,
            value=float(
                profile_value(
                    editing_profile,
                    "bullet",
                    "indent_left",
                    18.0,
                )
            ),
            step=1.0,
            key="style_bullet_indent",
        )

    with hanging_column:
        hanging_indent = st.number_input(
            "Hanging indent (pt)",
            min_value=0.0,
            max_value=100.0,
            value=float(
                profile_value(
                    editing_profile,
                    "bullet",
                    "hanging_indent",
                    10.0,
                )
            ),
            step=1.0,
            key="style_hanging_indent",
        )

    with nested_column:
        nested_indent = st.number_input(
            "Nested bullet increase (pt)",
            min_value=0.0,
            max_value=150.0,
            value=float(
                profile_value(
                    editing_profile,
                    "bullet",
                    "nested_indent_increment",
                    18.0,
                )
            ),
            step=1.0,
            key="style_nested_indent",
        )

    # Build overrides dictionary
    current_overrides = {
        "body": {
            "font": body_font.strip() or "Arial",
            "font_size": body_font_size,
            "line_spacing_points": line_spacing,
            "paragraph_spacing_after": paragraph_spacing,
        },
        "title": {
            "font": body_font.strip() or "Arial",
            "font_size": title_font_size,
        },
        "heading_1": {
            "font": body_font.strip() or "Arial",
            "font_size": heading_1_size,
        },
        "heading_2": {
            "font": body_font.strip() or "Arial",
            "font_size": heading_2_size,
        },
        "heading_3": {
            "font": body_font.strip() or "Arial",
            "font_size": heading_3_size,
        },
        "page": {
            "margin_left": margin_left,
            "margin_right": margin_right,
            "margin_top": margin_top,
            "margin_bottom": margin_bottom,
        },
        "bullet": {
            "font": body_font.strip() or "Arial",
            "font_size": body_font_size,
            "indent_left": bullet_indent,
            "hanging_indent": hanging_indent,
            "nested_indent_increment": nested_indent,
        },
    }

    save_column, rebuild_column = st.columns(2)

    with save_column:
        if st.button(
            "Save Style Overrides",
            use_container_width=True,
            key="save_style_overrides_button",
        ):
            try:
                save_json_file(
                    style_paths["overrides"],
                    current_overrides,
                )

                st.success(
                    "Manual style overrides were saved."
                )

            except Exception as error:
                st.error(
                    f"Could not save style overrides: {error}"
                )

    with rebuild_column:
        if st.button(
            "Save and Rebuild Profile",
            type="primary",
            use_container_width=True,
            key="rebuild_style_profile_button",
        ):
            try:
                save_json_file(
                    style_paths["overrides"],
                    current_overrides,
                )

                rebuilt_profile = (
                    rebuild_resolved_style_profile()
                )

                st.success(
                    "The resolved style profile was rebuilt successfully."
                )

                st.session_state[
                    "resolved_style_profile"
                ] = rebuilt_profile

                st.rerun()

            except Exception as error:
                st.error(
                    f"Could not rebuild the style profile: {error}"
                )

    if saved_overrides:
        with st.expander(
            "View Saved Manual Overrides",
            expanded=False,
        ):
            st.json(saved_overrides)

else:
    st.error(
        "No usable style profile is available. "
        "Add at least one PDF reference note and generate "
        "the detected style profile first."
    )

# Personalized notes section

st.divider()

st.header("6. Personalized Notes")

st.write(
    "Generate structured lecture notes from your edited transcript. "
    "The transcript is used as the factual source, while your previous "
    "notes provide examples of organization and formatting."
)

st.info(
    "Generation may take several minutes because retrieval, local Ollama "
    "generation, quality checking, and DOCX rendering all run on your computer."
)

# Current input status
current_transcript = (
    st.session_state.transcript.strip()
    if isinstance(st.session_state.transcript, str)
    else ""
)

existing_reference_notes = get_existing_reference_notes()
style_paths = get_style_profile_paths()
resolved_profile_exists = style_paths["resolved"].exists()

status_transcript, status_notes, status_profile = st.columns(3)

status_transcript.metric(
    "Edited transcript",
    "Ready" if current_transcript else "Missing",
)

status_notes.metric(
    "Reference notes",
    len(existing_reference_notes),
)

status_profile.metric(
    "Resolved style",
    "Ready" if resolved_profile_exists else "Missing",
)

# Prerequisite details
with st.expander(
    "Check Generation Prerequisites",
    expanded=False,
):
    if st.button(
        "Run Prerequisite Check",
        use_container_width=True,
        key="check_generation_prerequisites_button",
    ):
        try:
            with st.spinner(
                "Checking reference notes, style profile, Ollama, and model..."
            ):
                prerequisite_result = (
                    controller.check_note_generation_prerequisites()
                )

            st.session_state[
                "note_generation_prerequisites"
            ] = prerequisite_result

        except Exception as error:
            st.error(
                f"Prerequisite check failed: {error}"
            )

    prerequisite_result = st.session_state.get(
        "note_generation_prerequisites"
    )

    if prerequisite_result:
        if prerequisite_result.get("style_profile_exists"):
            st.success("Resolved style profile found.")
        else:
            st.error("Resolved style profile is missing.")

        reference_count = prerequisite_result.get(
            "reference_note_count",
            0,
        )

        if reference_count:
            st.success(
                f"{reference_count} reference note file(s) found."
            )
        else:
            st.error("No reference note files were found.")

        if prerequisite_result.get("ollama_running"):
            st.success("Ollama is running.")
        else:
            st.error(
                "Ollama is not running. Open the Ollama application "
                "before generating notes."
            )

        if prerequisite_result.get("model_available"):
            st.success("The configured Ollama model is available.")
        else:
            st.error(
                "The configured Ollama model is unavailable. "
                "Make sure llama3.2:3b is installed."
            )

# Optional output filename
custom_document_name = st.text_input(
    "Optional document filename",
    placeholder="Example: database_normalization_notes",
    help=(
        "Leave this empty to create a timestamped filename automatically. "
        "The .docx extension is added for you."
    ),
    key="generated_document_filename",
)

# Basic validation
missing_requirements = []

if not current_transcript:
    missing_requirements.append(
        "Save a non-empty edited transcript."
    )

if not existing_reference_notes:
    missing_requirements.append(
        "Add at least one PDF or TXT reference note."
    )

if not resolved_profile_exists:
    missing_requirements.append(
        "Create or rebuild the resolved style profile."
    )

generation_ready = not missing_requirements

if missing_requirements:
    st.warning(
        "The following requirements must be completed before generation:"
    )

    for requirement in missing_requirements:
        st.write(f"- {requirement}")

# Generate notes
generate_button = st.button(
    "Generate Formatted Notes",
    type="primary",
    disabled=not generation_ready,
    use_container_width=True,
    key="generate_formatted_notes_button",
)

if generate_button:
    progress = st.progress(0, text="Preparing note generation...")
    stage_message = st.empty()

    def update_generation_progress(percent: int, message: str) -> None:
        """Update Streamlit using safe stage messages from the service."""
        progress.progress(percent, text=message)
        stage_message.caption(message)

    try:
        clear_generated_note_state()
        filename = custom_document_name.strip() or None

        update_generation_progress(2, "Checking project prerequisites")
        prerequisite_result = controller.check_note_generation_prerequisites()

        if not prerequisite_result.get("ready"):
            problems = []
            if not prerequisite_result.get("style_profile_exists"):
                problems.append("the resolved style profile is missing")
            if not prerequisite_result.get("reference_note_count"):
                problems.append("no reference notes were found")
            if not prerequisite_result.get("ollama_running"):
                problems.append("Ollama is not running")
            if not prerequisite_result.get("model_available"):
                problems.append("the configured Ollama model is unavailable")
            raise RuntimeError(
                "Generation prerequisites are not ready: " + "; ".join(problems)
            )

        with st.spinner(
            "Generating, validating, and formatting your notes locally..."
        ):
            result = controller.generate_formatted_notes(
                edited_transcript=current_transcript,
                filename=filename,
                progress_callback=update_generation_progress,
            )

        st.session_state.generated_notes = result.get("structured_notes")
        st.session_state.generated_document_path = result.get("document_path")
        st.session_state.generation_sources = result.get("sources_used", [])
        st.session_state.retrieval_results = result.get("retrieval_results", [])
        st.session_state.generation_quality = result.get("quality")
        st.session_state.generation_style_profile = result.get("style_profile")

        update_generation_progress(100, "Formatted notes generated successfully")
        st.success("Your personalized formatted notes were generated successfully.")
        logger.info(
            "Streamlit generation workflow completed (sources=%d, retrieved=%d).",
            len(st.session_state.generation_sources),
            len(st.session_state.retrieval_results),
        )

    except TimeoutError as error:
        logger.warning("Formatted-note generation timed out: %s", error)
        progress.empty()
        stage_message.empty()
        st.error(
            "Generation timed out. Try a shorter transcript or increase the Ollama timeout."
        )
        with st.expander("Technical details"):
            st.write(str(error))

    except ConnectionError as error:
        logger.warning("Ollama connection failed during generation: %s", error)
        progress.empty()
        stage_message.empty()
        st.error("The application could not connect to Ollama. Make sure Ollama is running.")
        with st.expander("Technical details"):
            st.write(str(error))

    except FileNotFoundError as error:
        logger.warning("Required generation file was missing: %s", error)
        progress.empty()
        stage_message.empty()
        st.error("A required reference-note or style-profile file is missing.")
        with st.expander("Technical details"):
            st.write(str(error))

    except ValueError as error:
        logger.warning("Generation input or output validation failed: %s", error)
        progress.empty()
        stage_message.empty()
        st.error(
            "The notes could not be generated because some input or generated content was invalid."
        )
        with st.expander("Technical details"):
            st.write(str(error))

    except RuntimeError as error:
        logger.error("The generation pipeline could not complete: %s", error)
        progress.empty()
        stage_message.empty()
        st.error("The note-generation pipeline could not complete.")
        with st.expander("Technical details"):
            st.write(str(error))

    except Exception as error:
        logger.exception("Unexpected formatted-note generation failure.")
        progress.empty()
        stage_message.empty()
        st.error("An unexpected error occurred while generating the notes.")
        with st.expander("Technical details"):
            st.write(str(error))

# Generated results
if (
    st.session_state.generated_notes
    or st.session_state.generated_document_path
):
    st.divider()

    st.header("Generated Results")

    generated_notes = st.session_state.generated_notes
    document_path_value = (
        st.session_state.generated_document_path
    )
    quality = st.session_state.generation_quality
    sources = st.session_state.generation_sources
    retrieval_results = (
        st.session_state.retrieval_results
    )

    preview_tab, sources_tab, document_tab = st.tabs(
        [
            "📝 Note Preview",
            "🔎 Sources and Retrieval",
            "📄 Word Document",
        ]
    )

    # Structured note preview
    with preview_tab:
        st.subheader("Generated Note Preview")

        if isinstance(generated_notes, dict):
            display_structured_notes(
                generated_notes
            )
        else:
            st.warning(
                "No structured note preview is available."
            )

        if isinstance(quality, dict):
            st.divider()

            score = quality.get(
                "score",
                "Unknown",
            )

            passed = quality.get(
                "passed",
                False,
            )

            quality_column, status_column = st.columns(2)

            quality_column.metric(
                "Content-quality score",
                score,
            )

            status_column.metric(
                "Quality status",
                "Passed" if passed else "Needs review",
            )

            errors = quality.get(
                "errors",
                [],
            )

            warnings = quality.get(
                "warnings",
                [],
            )

            if errors:
                with st.expander(
                    "Content-quality errors",
                    expanded=True,
                ):
                    for error in errors:
                        st.error(error)

            if warnings:
                with st.expander(
                    "Content-quality warnings",
                    expanded=False,
                ):
                    for warning in warnings:
                        st.warning(warning)

            if not errors and not warnings:
                st.success(
                    "No content-quality problems were detected."
                )

    # Source transparency
    with sources_tab:
        st.subheader("Reference Sources Used")

        st.write(
            "These files influenced organization and writing style. "
            "The edited transcript remained the factual source."
        )

        if sources:
            for source in sources:
                st.write(f"- `{source}`")
        else:
            st.info(
                "No reference source filenames were returned."
            )

        st.subheader("Retrieved Note Chunks")

        if retrieval_results:
            with st.expander(
                "View retrieval scores and excerpts",
                expanded=False,
            ):
                for index, result in enumerate(
                    retrieval_results,
                    start=1,
                ):
                    if not isinstance(result, dict):
                        continue

                    source = result.get(
                        "source",
                        "Unknown source",
                    )

                    chunk_id = result.get(
                        "chunk_id",
                        "Unknown",
                    )

                    score = result.get(
                        "score",
                    )

                    text = result.get(
                        "text",
                        "",
                    )

                    st.markdown(
                        f"#### Result {index}"
                    )

                    st.write(
                        f"**Source:** `{source}`"
                    )

                    st.write(
                        f"**Chunk ID:** {chunk_id}"
                    )

                    if isinstance(score, (int, float)):
                        st.write(
                            f"**Similarity score:** "
                            f"{score:.4f}"
                        )
                    else:
                        st.write(
                            "**Similarity score:** unavailable"
                        )

                    if isinstance(text, str) and text.strip():
                        st.text_area(
                            "Retrieved excerpt",
                            value=text.strip(),
                            height=150,
                            disabled=True,
                            key=(
                                f"retrieval_preview_"
                                f"{index}_{chunk_id}"
                            ),
                        )

                    st.divider()
        else:
            st.info(
                "No retrieval results are available."
            )

    # DOCX result and download
    with document_tab:
        st.subheader("Formatted Word Document")

        if document_path_value:
            document_path = Path(
                document_path_value
            )

            if document_path.exists():
                st.success(
                    f"Document created: {document_path.name}"
                )

                st.caption(
                    f"Saved to: {document_path}"
                )

                try:
                    document_data = (
                        document_path.read_bytes()
                    )

                    st.download_button(
                        label="Download Formatted Notes",
                        data=document_data,
                        file_name=document_path.name,
                        mime=(
                            "application/vnd.openxmlformats-"
                            "officedocument.wordprocessingml.document"
                        ),
                        use_container_width=True,
                        key="download_generated_docx",
                    )

                except OSError as error:
                    st.error(
                        "The document exists, but it could "
                        "not be opened for download."
                    )

                    with st.expander(
                        "Technical details"
                    ):
                        st.write(str(error))

            else:
                st.warning(
                    "The generated document path is stored, "
                    "but the file could not be found on disk."
                )

        else:
            st.info(
                "No generated DOCX document is available."
            )