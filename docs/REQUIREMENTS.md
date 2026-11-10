# QuietScribe: requirements and acceptance

## Product goal

Local speech transcription with encrypted transcript storage. A reviewer should be able to install the package, run its tests, inspect its SQL boundaries and exercise the core workflow without a custom frontend.

## Functional requirements

- Local faster-whisper inference from an explicitly prepared model directory
- CPU int8 execution, speech segments and subtitle export
- Authenticated encryption with a fresh salt and nonce for each stored transcript
- A loopback API and CLI; no speech provider or API key is required

## Acceptance conditions

1. Missing model files must fail instead of downloading during transcription.
2. Stored vault bytes must not contain the plaintext transcript.
3. The wrong passphrase or altered ciphertext cannot decrypt successfully.
4. Subtitle timestamps must remain ordered and correctly carry milliseconds.

## Quality requirements

Persist domain state transactionally; validate untrusted inputs; keep provider failures visible; avoid credential and prompt disclosure in diagnostic errors; provide an installable Python package, authenticated API, container and repeatable automated checks. Keep fixture evidence distinct from public-data and live-provider evidence.

## Scope boundary

This is a Python local application rather than a browser PWA. Model preparation downloads weights once; transcription uses local files and does not upload audio to an inference provider. If the API is hosted remotely, uploaded audio reaches that host. Only vault transcripts are encrypted: source audio and explicitly exported subtitles remain the user's files. There is no passphrase recovery.

## Evaluation plan

Encryption, tamper detection, wrong passwords, storage privacy, subtitle boundaries, malformed audio and local-only model construction. A separate evidence file records one real CPU inference. External checks need the credentials, model files or network access described in the runbook. Before publishing quality claims, create a labelled evaluation set and report sample size, metric definition, model version and measured failures. Measure WER on a consented multi-speaker Hindi/English corpus; diarization and speaker attribution are not implemented.
