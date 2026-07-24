# AI Lecture Companion

## Overview

AI Lecture Companion is a Python application that records or uploads lecture audio and converts it into text using OpenAI Whisper. The long-term goal of the project is to generate personalized lecture notes by learning from a user's previous note-taking style through Retrieval-Augmented Generation (RAG) and a local language model.

This repository currently contains the completed Sprint 1 implementation.

---

## Current Features

- Record lecture audio using the laptop microphone
- Upload existing lecture recordings
- Transcribe audio using OpenAI Whisper (`small` model)
- Save recordings and transcripts automatically
- Simple Streamlit user interface
- Modular architecture using a central controller

---

## Project Structure

```text
FinalProject/
│
├── app.py                 # Streamlit user interface
├── config.py              # Project configuration and folder paths
├── requirements.txt
│
├── src/
│   ├── controller.py      # Coordinates application workflow
│   ├── recorder.py        # Audio recording
│   └── transcriber.py     # Whisper transcription
│
├── data/
│   ├── audio/             # Saved recordings
│   ├── transcripts/       # Generated transcripts
│   ├── notes/             # User notes (Sprint 2)
│   └── generated_notes/   # AI-generated notes (Sprint 2)
│
└── assets/
```

---

## Current Workflow

1. Record lecture audio or upload an existing recording.
2. Save the audio file.
3. Transcribe the recording using OpenAI Whisper.
4. Save the transcript as a text file.
5. Display the transcript in the Streamlit interface.

---

## Technologies

- Python
- Streamlit
- OpenAI Whisper
- SoundDevice
- SciPy
- NumPy

---

## Prerequisites

### Python

Python **3.11 or later** is recommended.

### FFmpeg

OpenAI Whisper requires **FFmpeg** to decode audio files. FFmpeg is **not** a Python package and must be installed separately before running the application.

### Windows

1. Download the **FFmpeg Essentials Build** from Gyan.dev:

   https://www.gyan.dev/ffmpeg/builds/

2. Download the latest **release essentials build** (ZIP format).

3. Extract the downloaded archive.

4. Open the extracted folder and locate the `bin` directory (for example, `ffmpeg-8.1.2-essentials_build\bin`).

5. Add the `bin` directory to your system's **PATH** environment variable.

6. Open a new Command Prompt or PowerShell window and verify the installation:

```bash
ffmpeg -version
```

If the version information is displayed, FFmpeg has been installed successfully.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

### macOS

```bash
brew install ffmpeg
```

Verify the installation:

```bash
ffmpeg -version
```

---

## Planned Features (Sprint 2)

- Import previous lecture notes
- Retrieve relevant note examples using semantic search (RAG)
- Generate personalized lecture notes with Ollama
- Automatic transcript cleanup
- Editable transcript before note generation

---

## Running the Project

### 1. Install Python dependencies

It is recommended to create and activate a virtual environment before installing the required packages.

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Verify FFmpeg

Ensure FFmpeg is installed correctly:

```bash
ffmpeg -version
```

If the version information is displayed, FFmpeg has been installed successfully.

### 3. Run the application

Start the Streamlit application:

```bash
streamlit run app.py
```

The application will open automatically in your default web browser. If it does not, open the URL displayed in the terminal (typically `http://localhost:8501`).
