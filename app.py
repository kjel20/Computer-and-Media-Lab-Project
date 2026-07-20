from datetime import datetime
from pathlib import Path
import streamlit as st
from config import AUDIO_DIR
from src.controller import LectureController

# Page configuration

st.set_page_config(
    page_title="AI Lecture Companion",
    page_icon="🎓",
    layout="wide",
)

# Session state

if "controller" not in st.session_state:
    with st.spinner("Loading Whisper model..."):
        st.session_state.controller = LectureController()

if "transcript" not in st.session_state:
    st.session_state.transcript = ""

if "audio_path" not in st.session_state:
    st.session_state.audio_path = None

if "transcript_path" not in st.session_state:
    st.session_state.transcript_path = None

controller = st.session_state.controller

# Helper function

def save_uploaded_audio(uploaded_file) -> Path:
    # Save an uploaded audio file inside the project's audio folder.

    safe_filename = Path(uploaded_file.name).name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = AUDIO_DIR / f"uploaded_{timestamp}_{safe_filename}"
    filepath.write_bytes(uploaded_file.getbuffer())

    return filepath

# Sidebar

with st.sidebar:
    st.header("Lecture Workflow")

    st.markdown(
        """
        1. Record or upload audio  
        2. Transcribe the lecture  
        3. Review the transcript  
        4. Generate personalized notes *(Sprint 2)*
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

                controller.set_audio_file(uploaded_path)

                st.session_state.audio_path = uploaded_path
                st.session_state.transcript = ""
                st.session_state.transcript_path = None

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
            transcript, transcript_path = (
                controller.transcribe_latest()
            )

        st.session_state.transcript = transcript
        st.session_state.transcript_path = transcript_path

        st.success("Transcription completed.")

    except Exception as error:
        st.error(f"Transcription failed: {error}")

# Transcript section

st.divider()

st.header("3. Lecture Transcript")

if st.session_state.transcript:
    st.text_area(
        "Transcript",
        value=st.session_state.transcript,
        height=350,
    )

    if st.session_state.transcript_path:
        transcript_path = Path(
            st.session_state.transcript_path
        )
        st.caption(
            f"Saved to: {transcript_path}"
        )
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

# Future Sprint 2 section

st.divider()

st.header("4. Personalized Notes")

st.info(
    "The next development stage will retrieve examples from your "
    "previous notes and use Ollama to generate new notes in your style."
)

st.button(
    "Generate Personalized Notes",
    disabled=True,
    use_container_width=True,
)