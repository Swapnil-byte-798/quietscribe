"""Local CPU inference and an authenticated, encrypted transcript vault."""

import hashlib
import json
import math
from pathlib import Path
import secrets
import subprocess
import threading
import time
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .runtime import Fault, Store, require

SCHEMA = """CREATE TABLE IF NOT EXISTS recordings(id TEXT PRIMARY KEY,audio_hash TEXT NOT NULL,
 payload BLOB NOT NULL,created REAL NOT NULL,duration REAL NOT NULL,model TEXT NOT NULL)"""


def seal(value: dict, password: str) -> bytes:
    password = require(password, "Vault passphrase", 1000)
    if len(password) < 12:
        raise Fault("Use a vault passphrase of at least 12 characters.")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300000, dklen=32)
    encrypted = AESGCM(key).encrypt(
        nonce, json.dumps(value, ensure_ascii=False).encode(), b"quietscribe-v1"
    )
    return b"QS01" + salt + nonce + encrypted


def unseal(payload: bytes, password: str) -> dict:
    if len(payload) < 48 or payload[:4] != b"QS01":
        raise Fault("Unsupported or corrupt vault record.")
    key = hashlib.pbkdf2_hmac(
        "sha256",
        require(password, "Vault passphrase", 1000).encode(),
        payload[4:20],
        300000,
        dklen=32,
    )
    try:
        return json.loads(
            AESGCM(key).decrypt(payload[20:32], payload[32:], b"quietscribe-v1")
        )
    except (InvalidTag, ValueError, UnicodeError):
        raise Fault("Incorrect passphrase or modified encrypted record.", 401) from None


def srt_time(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise Fault("Subtitle time must be finite and nonnegative.")
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    whole, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{milliseconds:03}"


def export_srt(segments: list[dict]) -> str:
    lines = []
    last_end = 0.0
    for index, segment in enumerate(segments, 1):
        start = float(segment["start"])
        end = float(segment["end"])
        if start < last_end - 0.01 or end < start:
            raise Fault("Transcript segment timing is inconsistent.")
        lines.extend(
            [
                str(index),
                f"{srt_time(start)} --> {srt_time(end)}",
                require(segment["text"], "Segment", 10000),
                "",
            ]
        )
        last_end = end
    return "\n".join(lines)


def inspect_audio(path: Path) -> dict:
    if not path.is_file() or not 1 <= path.stat().st_size <= 100_000_000:
        raise Fault("Choose a local audio file of at most 100 MB.")
    try:
        raw = subprocess.run(
            [
                "ffprobe",
                "-protocol_whitelist",
                "file,pipe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,sample_rate,channels",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        info = json.loads(raw.stdout)
        duration = float(info["format"]["duration"])
        if (
            not any(stream.get("codec_type") == "audio" for stream in info["streams"])
            or not math.isfinite(duration)
            or not 0 < duration <= 1800
        ):
            raise ValueError("Invalid audio duration")
        return {"duration": duration, "bytes": path.stat().st_size}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise Fault(
            "Use readable audio up to 30 minutes; FFmpeg/ffprobe must be installed."
        ) from None


class Transcriber:
    def __init__(self, model_path: str):
        self.path = Path(model_path)
        if not self.path.is_dir() or not (self.path / "model.bin").is_file():
            raise Fault(
                "Prepare local Whisper weights and supply their directory. Transcription never downloads a model implicitly.",
                503,
            )
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            str(self.path), device="cpu", compute_type="int8", local_files_only=True
        )
        self.lock = threading.Lock()

    def transcribe(self, path: Path, language: str | None = None) -> dict:
        metadata = inspect_audio(path)
        import numpy as np

        try:
            decoded = subprocess.run(
                [
                    "ffmpeg",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-v",
                    "error",
                    "-i",
                    str(path),
                    "-t",
                    "1800",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "f32le",
                    "-",
                ],
                capture_output=True,
                check=True,
                timeout=90,
            )
            audio = np.frombuffer(decoded.stdout, dtype=np.float32)
            if not len(audio):
                raise ValueError("No audio samples")
        except (OSError, subprocess.SubprocessError, ValueError):
            raise Fault("FFmpeg could not decode the recording.") from None
        with self.lock:
            segments, info = self.model.transcribe(
                audio,
                language=language,
                vad_filter=True,
                word_timestamps=True,
                beam_size=5,
            )
            values = [
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment.text.strip(),
                    "words": [
                        {
                            "start": float(word.start),
                            "end": float(word.end),
                            "word": word.word,
                        }
                        for word in (segment.words or [])
                    ],
                }
                for segment in segments
                if segment.text.strip()
            ]
        return {
            "text": " ".join(value["text"] for value in values),
            "segments": values,
            "duration": metadata["duration"],
            "language": info.language,
            "model": self.path.name,
            "inference": "local_cpu_int8",
            "audio_uploaded": False,
        }


class Vault:
    def __init__(self, path=".data/quietscribe.db"):
        self.store = Store(path, SCHEMA)

    def save(self, transcript: dict, audio: bytes, password: str) -> str:
        if not isinstance(transcript, dict) or not isinstance(
            transcript.get("segments"), list
        ):
            raise Fault("Invalid transcript.")
        export_srt(transcript["segments"])
        encrypted = seal(transcript, password)
        identifier = str(uuid4())
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO recordings VALUES(?,?,?,?,?,?)",
                (
                    identifier,
                    hashlib.sha256(audio).hexdigest(),
                    encrypted,
                    time.time(),
                    transcript["duration"],
                    transcript["model"],
                ),
            )
        return identifier

    def load(self, identifier, password):
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM recordings WHERE id=?", (identifier,)
            ).fetchone()
        if row is None:
            raise Fault("Transcript not found.", 404)
        return unseal(row["payload"], password)

    def export(self, identifier, password, format="txt"):
        transcript = self.load(identifier, password)
        if format == "txt":
            return transcript["text"]
        if format == "srt":
            return export_srt(transcript["segments"])
        if format == "json":
            return json.dumps(transcript, indent=2, ensure_ascii=False)
        raise Fault("Choose txt, srt, or json.")
