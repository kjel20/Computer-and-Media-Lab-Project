from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from config import AUDIO_DIR


class Recorder:
    """
    Records audio from the default microphone
    and saves it as a WAV file.
    """

    def __init__(self):
        self.sample_rate = 44100 # CD quality audio
        self.channels = 1 # mono, as stereo isn't necessary
        self.frames = []
        self.recording = False
        self.stream = None

    def _callback(self, indata, frames, time, status):
        # Called automatically while recording

        if status:
            print(status)

        if self.recording:
            self.frames.append(indata.copy())

    def start_recording(self):
        self.frames.clear()
        self.recording = True

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.int16,
            callback=self._callback,
        )
        self.stream.start()

    def stop_recording(self):
        self.recording = False

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()

    def save_recording(self) -> Path:
        if len(self.frames) == 0:
            raise ValueError("No audio has been recorded.")

        audio = np.concatenate(self.frames)

        filename = (
            f"lecture_{datetime.now():%Y%m%d_%H%M%S}.wav"
        )

        filepath = AUDIO_DIR / filename

        write(
            filepath,
            self.sample_rate,
            audio,
        )
        return filepath