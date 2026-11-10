import os
from pathlib import Path
import tempfile
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, SecretStr
import base64
from .runtime import Fault, make_app, settings
from .service import Transcriber, Vault

app, auth, reviewer = make_app("QuietScribe")


class Audio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_base64: str = Field(min_length=1, max_length=140_000_000)
    passphrase: SecretStr
    language: str | None = None


class Unlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passphrase: SecretStr
    format: str = "txt"


def vault():
    return Vault(Path(os.environ.get("DATA_DIR", ".data")) / "quietscribe.db")


@app.post("/transcribe", dependencies=[Depends(auth)])
def transcribe(body: Audio):
    try:
        audio = base64.b64decode(body.audio_base64, validate=True)
    except ValueError:
        raise Fault("Invalid base64 audio.") from None
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audio"
        path.write_bytes(audio)
        transcript = Transcriber(settings().get("WHISPER_MODEL_PATH", "")).transcribe(
            path, body.language
        )
    identifier = vault().save(transcript, audio, body.passphrase.get_secret_value())
    return {
        "id": identifier,
        "text": transcript["text"],
        "audio_uploaded_to_provider": False,
    }


@app.post("/recordings/{identifier}/export", dependencies=[Depends(auth)])
def export(identifier: str, body: Unlock):
    return {
        "content": vault().export(
            identifier, body.passphrase.get_secret_value(), body.format
        )
    }
