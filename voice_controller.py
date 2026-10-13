#!/usr/bin/env python3
"""Objective 4 backend: voice capture and Whisper transcription.

The Streamlit UI in voice_app.py calls capture_voice_intent(); nothing here
imports Streamlit, so the backend stays usable from plain Python too.
"""

import tempfile
import wave
from pathlib import Path

import requests
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"  # full model: most accurate Groq STT; turbo is faster but weaker


def record_microphone(duration=5, rate=16000):
    """Record mono audio from the laptop mic; returns (pcm_bytes, rate)."""
    import pyaudio
    mic = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1, rate=rate,
                      input=True, frames_per_buffer=1024)
    frames = [stream.read(1024, exception_on_overflow=False)
              for _ in range(int(rate / 1024 * duration))]
    stream.stop_stream()
    stream.close()
    mic.terminate()
    return b"".join(frames), rate


def save_wav(pcm_bytes, rate=16000):
    """Save raw PCM bytes as a temp WAV file; returns its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm_bytes)
    return tmp.name


def transcribe_wav(path):
    """Send a WAV file to Groq Whisper and return the transcribed text."""
    config = dotenv_values(HERE / ".env")
    if not config.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is missing from lab7/.env.")
    with open(path, "rb") as audio:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": "Bearer " + config["GROQ_API_KEY"]},
            files={"file": ("intent.wav", audio, "audio/wav")},
            data={"model": GROQ_MODEL, "response_format": "json", "language": "en"},
            timeout=(10, 30),
        )
    if not response.ok:
        raise RuntimeError(f"Transcription returned HTTP {response.status_code}.")
    return response.json()["text"].strip()


def capture_voice_intent(duration=5, audio_bytes=None):
    """Record audio from the mic for duration seconds (default 5), save it as
    a temp WAV file, transcribe it via Whisper, and return the text string.

    Pass audio_bytes (recorded WAV/WEBM data, e.g. from the Streamlit mic
    widget) to skip the microphone and transcribe those bytes directly.
    """
    if audio_bytes is None:
        pcm, rate = record_microphone(duration)
        path = save_wav(pcm, rate)
    else:
        suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".webm"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(audio_bytes)
        tmp.close()
        path = tmp.name
    return transcribe_wav(path)
