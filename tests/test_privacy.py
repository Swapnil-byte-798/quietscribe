from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import wave
from quietscribe.runtime import Fault
from quietscribe.service import (
    Vault,
    Transcriber,
    export_srt,
    inspect_audio,
    seal,
    srt_time,
    unseal,
)


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.vault = Vault(Path(self.directory.name) / "vault.db")
        self.transcript = {
            "text": "Private meeting notes",
            "segments": [{"start": 0, "end": 1.5, "text": "Private meeting notes"}],
            "duration": 1.5,
            "model": "test-fixture",
        }
        self.password = "a long private passphrase"

    def tearDown(self):
        self.directory.cleanup()

    def test_encryption_roundtrip(self):
        self.assertEqual(
            unseal(seal(self.transcript, self.password), self.password), self.transcript
        )

    def test_ciphertext_contains_no_transcript(self):
        self.assertNotIn(b"Private meeting notes", seal(self.transcript, self.password))

    def test_random_nonce_changes_ciphertext(self):
        self.assertNotEqual(
            seal(self.transcript, self.password), seal(self.transcript, self.password)
        )

    def test_wrong_password_rejected(self):
        with self.assertRaises(Fault):
            unseal(seal(self.transcript, self.password), "wrong password")

    def test_ciphertext_tampering_rejected(self):
        encrypted = bytearray(seal(self.transcript, self.password))
        encrypted[-1] ^= 1
        with self.assertRaises(Fault):
            unseal(bytes(encrypted), self.password)

    def test_short_password_rejected(self):
        with self.assertRaises(Fault):
            seal(self.transcript, "short")

    def test_vault_persists_across_service_restart(self):
        identifier = self.vault.save(self.transcript, b"audio", self.password)
        self.assertEqual(
            Vault(self.vault.store.path).load(identifier, self.password),
            self.transcript,
        )

    def test_wrong_record_does_not_leak(self):
        with self.assertRaises(Fault):
            self.vault.load("missing", self.password)

    def test_srt_export(self):
        identifier = self.vault.save(self.transcript, b"audio", self.password)
        self.assertIn(
            "00:00:00,000 --> 00:00:01,500",
            self.vault.export(identifier, self.password, "srt"),
        )

    def test_time_rounding_carries_to_next_second(self):
        self.assertEqual(srt_time(59.9996), "00:01:00,000")

    def test_invalid_timestamps(self):
        for value in [-1, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(Fault):
                srt_time(value)

    def test_reversed_segment_rejected(self):
        with self.assertRaises(Fault):
            export_srt([{"start": 2, "end": 1, "text": "invalid"}])

    def test_local_model_required_before_inference(self):
        with self.assertRaises(Fault):
            Transcriber(str(Path(self.directory.name) / "missing-model"))

    def test_ffprobe_validates_actual_wave(self):
        path = Path(self.directory.name) / "sample.wav"
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\0\0" * 16000)
        self.assertAlmostEqual(inspect_audio(path)["duration"], 1.0, places=2)

    def test_invalid_audio_rejected(self):
        path = Path(self.directory.name) / "bad.wav"
        path.write_bytes(b"not audio")
        with self.assertRaises(Fault):
            inspect_audio(path)

    def test_duplicate_audio_does_not_overwrite_other_password(self):
        first = self.vault.save(self.transcript, b"same-audio", self.password)
        second = self.vault.save(
            self.transcript, b"same-audio", "another long passphrase"
        )
        self.assertNotEqual(first, second)
        self.assertEqual(self.vault.load(first, self.password), self.transcript)
