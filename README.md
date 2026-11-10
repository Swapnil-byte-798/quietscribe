# QuietScribe

Local speech transcription with encrypted transcript storage.

[![Python verification](https://github.com/Swapnil-byte-798/quietscribe/actions/workflows/ci.yml/badge.svg)](https://github.com/Swapnil-byte-798/quietscribe/actions/workflows/ci.yml)

Project 8 in a Python and SQL AI engineering portfolio. The interface is a Python CLI and FastAPI's generated API documentation.

## What works

- Local faster-whisper inference from an explicitly prepared model directory
- CPU int8 execution, speech segments and subtitle export
- Authenticated encryption with a fresh salt and nonce for each stored transcript
- A loopback API and CLI; no speech provider or API key is required

## Run it

Python 3.11 or 3.12, FFmpeg/ffprobe and a local CTranslate2 Whisper model. The container includes FFmpeg. Audio is limited to 100 MB and thirty minutes.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m quietscribe demo
python -m quietscribe setup
python -m quietscribe serve --port 8020
```

Open http://127.0.0.1:8020/docs. `setup` prompts for credentials without displaying them, generates independent operator/reviewer tokens, and stores them in an ignored file with owner-only permissions. Use the operator token as `Authorization: Bearer ...`; account, client and tenant endpoints issue their own scoped tokens. Do not commit any of these values.

The demo is explicitly labelled: authored fixtures exercise the workflow, not a live provider. `check-keys` reports configuration only and never claims a provider has been validated.

## Credentials

No external API key. Choose a vault passphrase of at least 12 characters when transcribing.

To reuse a provider key across these repositories, run `python -m quietscribe setup --shared` before the local `setup` command. The shared prompt adds missing keys and preserves existing nonempty keys. Local environment variables take precedence. See [.env.example](.env.example) for names only; real keys are never shipped.

## Design and boundaries

Local audio → FFmpeg decoding → local Whisper CPU inference → AES-GCM vault → explicit TXT/SRT export

This is a Python local application rather than a browser PWA. Model preparation downloads weights once; transcription uses local files and does not upload audio to an inference provider. If the API is hosted remotely, uploaded audio reaches that host. Only vault transcripts are encrypted: source audio and explicitly exported subtitles remain the user's files. There is no passphrase recovery.

## Verification

Encryption, tamper detection, wrong passwords, storage privacy, subtitle boundaries, malformed audio and local-only model construction. A separate evidence file records one real CPU inference. Common tests also cover hidden setup, configuration precedence, provider response validation, API authentication and transactional rollback.

[Verification record](evidence/verification.json) separates automated checks from provider-dependent acceptance. No result represents all possible inputs, production load, or a calibrated model-quality benchmark.

## Read further

- [Requirements and acceptance](docs/REQUIREMENTS.md)
- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Runbook and key setup](docs/RUNBOOK.md)
- [Study guide](docs/STUDY_GUIDE.md)

## Next engineering milestone

Measure WER on a consented multi-speaker Hindi/English corpus; diarization and speaker attribution are not implemented.

## Prepare a model and transcribe

```bash
python -m quietscribe prepare-model --size tiny --directory .models/whisper-tiny
python -m quietscribe transcribe /path/to/recording.wav --model-path .models/whisper-tiny --output artifacts/transcript.srt
```

Model preparation uses the network explicitly. Transcription only reads local weights and prompts for the vault passphrase. For the API, set WHISPER_MODEL_PATH to that model directory. The SRT export is a plaintext file chosen explicitly by this command.
