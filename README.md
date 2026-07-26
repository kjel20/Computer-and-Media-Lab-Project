# AI Lecture Companion

## Overview

AI Lecture Companion is a Python application that records or uploads lecture audio, transcribes it using OpenAI Whisper, and automatically generates personalized, well-formatted lecture notes using a local large language model (Ollama).

Unlike traditional transcription tools, the application learns a user's organizational note-taking style from previous lecture notes. It combines Retrieval-Augmented Generation (RAG), PDF style extraction, semantic retrieval, structured JSON generation, content-quality validation, and automatic Microsoft Word document generation to produce notes that resemble the user's own writing style while remaining factually grounded in the edited lecture transcript.

The project was developed for the Computer and Media Lab course.

---

# Features

## Audio Processing

- Record lecture audio using the microphone
- Upload existing lecture recordings
- Support for multiple audio formats
- Automatic audio validation
- Automatic saving of recordings

---

## Transcription

- Transcribe lectures using OpenAI Whisper (`small` model)
- Save transcripts automatically
- Edit transcripts before note generation
- Prevent empty or invalid transcript generation

---

## Reference Note Library

- Upload multiple PDF and TXT reference notes
- Safe filename handling (no accidental overwriting)
- Automatic note chunking
- PDF text extraction using **PyMuPDF**
- TXT support for content-only reference notes

---

## Style Learning

The application learns the user's note-taking style by analysing uploaded PDF notes.

It extracts:

- fonts
- font sizes
- text colours
- page margins
- indentation
- heading hierarchy
- line spacing
- paragraph spacing
- bullet indentation

The detected style can be manually adjusted within the Streamlit interface before note generation.

---

## Retrieval-Augmented Generation (RAG)

Reference notes are indexed using Sentence Transformers.

For every lecture, the application:

- embeds the edited transcript
- retrieves semantically similar note chunks
- falls back to organizational examples if similarity is low
- uses retrieved notes only for writing style and organization

The edited transcript always remains the factual source.

---

## AI Note Generation

Uses a local Ollama model (`llama3.2:3b`) to generate structured lecture notes.

The generation pipeline includes:

- prompt building
- JSON schema enforcement
- hallucination prevention
- JSON repair
- content-quality validation
- automatic quality repair (one retry if needed)

---

## DOCX Generation

Generated notes are automatically formatted into Microsoft Word documents.

Formatting includes:

- page margins
- title
- subtitle (only when appropriate)
- headings
- paragraphs
- bullets
- nested bullets
- definitions
- examples
- summaries
- fonts
- font sizes
- colours
- spacing
- indentation

The generated documents closely imitate the formatting of the uploaded reference notes.

---

## Streamlit Interface

The application provides an interactive interface for:

- recording lectures
- uploading audio
- uploading reference notes
- editing transcripts
- managing style profiles
- generating formatted notes
- previewing structured notes
- downloading DOCX files
- viewing retrieval information
- monitoring progress

---

## Logging

The application performs structured logging throughout the pipeline.

Logs include:

- application startup
- recording
- transcription
- retrieval
- generation
- rendering
- quality validation

Transcript contents, prompts, retrieved notes, and generated notes are never written to the log.

---

# Technologies

- Python
- Streamlit
- OpenAI Whisper
- Ollama
- Sentence Transformers
- PyMuPDF
- python-docx
- SoundDevice
- NumPy
- SciPy
- PyTorch

---

# Project Structure

```text
AI_Lecture_Companion/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── content_quality.py
│   ├── controller.py
│   ├── docx_renderer.py
│   ├── generator.py
│   ├── logging_config.py
│   ├── note_generation_service.py
│   ├── note_library.py
│   ├── note_schema.py
│   ├── progress.py
│   ├── prompt_builder.py
│   ├── prompt_templates.py
│   ├── recorder.py
│   ├── retriever.py
│   ├── style_extractor.py
│   ├── style_profile.py
│   ├── style_resolver.py
│   └── transcriber.py
│
├── tests/
│   ├── test_content_quality.py
│   ├── test_controller.py
│   ├── test_docx_renderer.py
│   ├── test_note_schema.py
│   └── test_style_resolver.py
│
├── data/
│   ├── audio/
│   ├── generated_documents/
│   ├── notes/
│   ├── style_profiles/
│   └── transcripts/
│
└── logs/
```

---

# File Descriptions

## Root Files

| File | Purpose |
|-------|----------|
| **app.py** | Streamlit user interface |
| **config.py** | Central project configuration |
| **requirements.txt** | Python dependencies |
| **README.md** | Project documentation |
| **.gitignore** | Git ignore rules |

---

## Source Files

### controller.py

Coordinates the application's workflow and acts as the bridge between the user interface and backend services.

---

### recorder.py

Handles microphone recording, audio validation, and saving recordings.

---

### transcriber.py

Uses OpenAI Whisper to convert lecture audio into editable text transcripts.

---

### note_library.py

Loads reference notes from PDFs and TXT files and divides them into retrieval chunks.

---

### style_extractor.py

Extracts visual formatting information from PDF notes using PyMuPDF.

---

### style_profile.py

Builds a representative formatting profile from multiple reference notes.

---

### style_resolver.py

Applies manual overrides and fallback values to produce the final formatting profile.

---

### retriever.py

Indexes note chunks using Sentence Transformers and retrieves relevant organizational examples.

---

### prompt_templates.py

Contains reusable prompt templates used during note generation and repair.

---

### prompt_builder.py

Constructs the complete prompt supplied to Ollama.

---

### note_schema.py

Defines the structured JSON format expected from the language model and validates generated notes.

---

### content_quality.py

Evaluates generated notes for completeness, placeholder content, and overall quality.

---

### generator.py

Communicates with Ollama, validates responses, performs JSON repair, and applies content-quality repair.

---

### docx_renderer.py

Converts structured notes into formatted Microsoft Word documents.

---

### note_generation_service.py

Coordinates the complete personalized note-generation pipeline.

---

### logging_config.py

Configures application logging and log rotation.

---

### progress.py

Provides shared progress callbacks used throughout the generation pipeline.

---

# Application Workflow

1. Record or upload lecture audio.
2. Transcribe the lecture using Whisper.
3. Review and edit the transcript.
4. Upload reference notes.
5. Extract formatting information.
6. Build the resolved style profile.
7. Chunk and index reference notes.
8. Retrieve organizational examples.
9. Build the Ollama prompt.
10. Generate structured lecture notes.
11. Validate and repair JSON if necessary.
12. Perform content-quality validation.
13. Render a formatted DOCX document.
14. Preview and download the generated notes.

---

# Prerequisites

## Python

Python **3.11 or later** is recommended.

---

## FFmpeg

OpenAI Whisper requires **FFmpeg**.

### Windows

1. Download the **FFmpeg Essentials Build** from:

https://www.gyan.dev/ffmpeg/builds/

2. Extract the archive.

3. Locate the `bin` folder.

4. Add the `bin` folder to the system PATH.

Verify installation:

```bash
ffmpeg -version
```

---

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

---

### macOS

```bash
brew install ffmpeg
```

Verify:

```bash
ffmpeg -version
```

---

## Ollama

Install Ollama from:

https://ollama.com/

After installation, download the model used by the project:

```bash
ollama pull llama3.2:3b
```

Ensure the Ollama server is running before generating notes.

---

# Installation

Create a virtual environment (recommended):

```bash
python -m venv venv
```

Activate it.

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Running the Application

Launch Streamlit:

```bash
streamlit run app.py
```

The application will open in your browser.

---

# Using the Application

1. Upload your reference notes (PDF recommended).
2. Record or upload lecture audio.
3. Generate the transcript.
4. Edit the transcript if necessary.
5. Review or adjust the detected style profile.
6. Generate formatted lecture notes.
7. Preview the generated notes.
8. Download the DOCX document.

---

# Data Directories

| Folder | Purpose |
|---------|----------|
| `data/audio/` | Saved recordings |
| `data/transcripts/` | Saved transcripts |
| `data/notes/` | User reference notes |
| `data/style_profiles/` | Detected, override, and resolved style profiles |
| `data/generated_documents/` | Generated Word documents |
| `logs/` | Application log files |

---

# Running Tests

Run the automated unit tests:

```bash
python -m pytest tests -v
```

or

```bash
python -m pytest tests -q
```

---

# Limitations

- PDF formatting extraction depends on the quality of the source PDF.
- TXT files provide content but not formatting information.
- Generated notes imitate writing style rather than copying previous notes.
- The quality of generated notes depends on the quality of the transcript.
- Note generation can sometimes still fail. Click the "Generate Formatted Notes" button again to re-try, or try rerunning the streamlit app.
- Ollama must be installed locally.
- The application currently generates Microsoft Word documents only.

---

This project was developed as part of the **Computer and Media Lab** course for educational purposes.
