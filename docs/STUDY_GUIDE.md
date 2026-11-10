# QuietScribe: study guide

## Explain the problem

Local speech transcription with encrypted transcript storage. Explain who uses the workflow and why each confirmation, isolation or validation boundary exists before describing libraries.

## Read the implementation

1. Read `service.py` and its SQL schema. Name the durable entities and draw their valid state transitions.
2. Trace one successful API request from its Pydantic input to its committed writes.
3. Trace a provider failure and identify what can and cannot be rolled back.
4. Read the tests that enforce the acceptance conditions below. Explain why each failure would matter to a user.

1. Missing model files must fail instead of downloading during transcription.
2. Stored vault bytes must not contain the plaintext transcript.
3. The wrong passphrase or altered ciphertext cannot decrypt successfully.
4. Subtitle timestamps must remain ordered and correctly carry milliseconds.

## Interview discussion

- Where is the transaction boundary, and what happens if the process dies immediately after it?
- How are retries bound to the original request? Which operation can safely repeat?
- Which inputs are untrusted, and how are externally generated fields validated?
- What is tested with fixtures, what was measured on public data, and what remains unmeasured?
- What would change with ten times the data, multiple workers, or another tenant?

## Honest project explanation

Describe the implemented behavior, then demonstrate a representative test and explain its failure condition. Do not present mock latency, authored examples, uncalibrated scores or optional integrations as measured production results.

Known boundaries: This is a Python local application rather than a browser PWA. Model preparation downloads weights once; transcription uses local files and does not upload audio to an inference provider. If the API is hosted remotely, uploaded audio reaches that host. Only vault transcripts are encrypted: source audio and explicitly exported subtitles remain the user's files. There is no passphrase recovery.

## Practical extension

Measure WER on a consented multi-speaker Hindi/English corpus; diarization and speaker attribution are not implemented. Define a measurable acceptance criterion before extending the implementation.
