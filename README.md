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

```
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

## Planned Features (Sprint 2)

- Import previous lecture notes
- Retrieve relevant note examples using semantic search (RAG)
- Generate personalized lecture notes with Ollama
- Automatic transcript cleanup for better speech recognition
- Editable transcript before note generation

---

## Running the Project

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
streamlit run app.py
```
