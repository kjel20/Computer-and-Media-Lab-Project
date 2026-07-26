from datetime import datetime
from pathlib import Path
import logging
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from config import (
    AUDIO_CHANNELS,
    AUDIO_DIR,
    AUDIO_SAMPLE_RATE,
)

logger = logging.getLogger(__name__)

class Recorder:
    """
    Records audio from the default microphone
    and saves it as a WAV file.
    """

    def __init__(self):
        self.sample_rate = AUDIO_SAMPLE_RATE
        self.channels = AUDIO_CHANNELS
        self.frames = []
        self.recording = False
        self.stream = None

    def _callback(self, indata, frames, time, status):
        """
        Receive audio data while the microphone stream is active.
        This method is called automatically by SoundDevice.
        """

        if status:
            logger.warning(
                "Audio recording status: %s",
                status,
            )

        if self.recording:
            self.frames.append(indata.copy())

    def start_recording(self) -> None:
        """
        Start recording audio from the default microphone.
        """

        if self.recording:
            raise RuntimeError(
                "Recording is already in progress."
            )

        self.frames.clear()
        self.recording = True

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.int16,
                callback=self._callback,
            )
            self.stream.start()
            logger.info("Audio recording started.")

        except Exception:
            self.recording = False
            self.stream = None
            logger.exception(
                "Failed to start microphone recording."
            )
            raise

    def stop_recording(self) -> None:
        """
        Stop the current microphone recording.
        """

        if not self.recording:
            raise RuntimeError(
                "No recording is currently in progress."
            )

        self.recording = False

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()

                logger.info("Audio recording stopped.")

            except Exception:
                logger.exception(
                    "Failed to stop the microphone stream."
                )
                raise

            finally:
                self.stream = None

    def save_recording(self) -> Path:
        """
        Save the recorded audio as a timestamped WAV file.

        Returns
        -------
        Path
            Path to the saved audio file.
        """

        if self.recording:
            raise RuntimeError(
                "Stop the recording before saving it."
            )

        if len(self.frames) == 0:
            raise ValueError(
                "No audio has been recorded."
            )

        try:
            audio = np.concatenate(
                self.frames,
                axis=0,
            )

        except ValueError as error:
            logger.exception(
                "Recorded audio frames could not be combined."
            )
            raise ValueError(
                "The recorded audio data is invalid."
            ) from error

        filename = (
            f"lecture_{datetime.now():%Y%m%d_%H%M%S}.wav"
        )

        filepath = AUDIO_DIR / filename

        try:
            write(
                filepath,
                self.sample_rate,
                audio,
            )
            logger.info(
                "Audio recording saved (file=%s, samples=%d).",
                filepath.name,
                len(audio),
            )

        except Exception:
            logger.exception(
                "Failed to save audio recording."
            )
            raise
        return filepath