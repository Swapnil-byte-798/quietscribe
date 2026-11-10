# QuietScribe: architecture

## Request and data path

Local audio → FFmpeg decoding → local Whisper CPU inference → AES-GCM vault → explicit TXT/SRT export

`api.py` validates transport input and credentials. `service.py` owns domain invariants and SQL transitions. `runtime.py` supplies small, vendored transport/configuration conventions so the repository can install independently. `cli.py` exposes setup, a labelled demo and serving commands. SQL schemas live beside the service that owns them.

## Decisions

Python and SQL keep the project aligned with the portfolio's existing skills. FastAPI supplies an inspectable contract without authored web code. SQLite provides a durable, low-cost local path; it is not a distributed database. The service owns transaction boundaries rather than spreading writes across API handlers. Domain services accept provider fixtures for tests; production commands never replace failed upstream calls with fixtures.

Provider keys come from owner-only files or the process environment. Tokens are distinct from provider keys. Never put a provider key into a public API client's configuration. Concurrent SQL writes are admitted transactionally; processes that die during external work can require operator recovery rather than unsafe automatic replay.

## Failure boundaries

1. Missing model files must fail instead of downloading during transcription.
2. Stored vault bytes must not contain the plaintext transcript.
3. The wrong passphrase or altered ciphertext cannot decrypt successfully.
4. Subtitle timestamps must remain ordered and correctly carry milliseconds.

Missing credentials return a configuration failure. Invalid provider structures fail validation. Network requests have timeouts and no silent retries through the common JSON client. An upstream timeout can still consume provider tokens; local rollback cannot undo external billing.

## Capacity and security limits

This is a Python local application rather than a browser PWA. Model preparation downloads weights once; transcription uses local files and does not upload audio to an inference provider. If the API is hosted remotely, uploaded audio reaches that host. Only vault transcripts are encrypted: source audio and explicitly exported subtitles remain the user's files. There is no passphrase recovery.

Bind locally for development. Before external hosting, add TLS, gateway request-size limits, restricted egress, protected persistent storage, retention policies and a process-specific secret store. No internet-facing deployment or production security certification is claimed by this repository.
