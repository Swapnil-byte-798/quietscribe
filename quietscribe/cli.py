from getpass import getpass
from pathlib import Path
import tempfile
from .runtime import run_cli
from .service import Transcriber, Vault


def demo():
    value = {
        "text": "An authored privacy test.",
        "segments": [{"start": 0, "end": 2, "text": "An authored privacy test."}],
        "duration": 2,
        "model": "authored-text-fixture",
    }
    with tempfile.TemporaryDirectory() as directory:
        vault = Vault(Path(directory) / "test.db")
        identifier = vault.save(value, b"fixture-audio", "fixture passphrase only")
        return {
            "mode": "encrypted_vault_fixture",
            "txt": vault.export(identifier, "fixture passphrase only"),
            "srt": vault.export(identifier, "fixture passphrase only", "srt"),
            "speech_model_run": False,
        }


def extend(sub):
    prepare = sub.add_parser("prepare-model")
    prepare.add_argument("--size", choices=["tiny", "base", "small"], default="tiny")
    prepare.add_argument("--directory", type=Path, default=Path(".models/whisper-tiny"))

    def prepare_action(args):
        from huggingface_hub import snapshot_download
        from .runtime import Fault

        if args.directory.exists() and any(args.directory.iterdir()):
            raise Fault(
                "Choose an empty model directory to avoid mixing weight versions."
            )
        try:
            snapshot_download(
                "Systran/faster-whisper-" + args.size, local_dir=str(args.directory)
            )
        except Exception:
            raise Fault(
                "Model preparation failed; check network access and retry into an empty directory.",
                502,
            ) from None
        return {
            "model_path": str(args.directory.resolve()),
            "audio_uploaded": False,
            "downloaded_weights": True,
        }

    prepare.set_defaults(action=prepare_action)
    transcribe = sub.add_parser("transcribe")
    transcribe.add_argument("path", type=Path)
    transcribe.add_argument("--model-path", required=True)
    transcribe.add_argument("--language")
    transcribe.add_argument(
        "--output", type=Path, default=Path("artifacts/transcript.srt")
    )

    def action(args):
        password = getpass("Vault passphrase (hidden, at least 12 characters): ")
        transcript = Transcriber(args.model_path).transcribe(args.path, args.language)
        vault = Vault()
        identifier = vault.save(transcript, args.path.read_bytes(), password)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(vault.export(identifier, password, "srt"))
        return {
            "recording_id": identifier,
            "text": transcript["text"],
            "language": transcript["language"],
            "audio_uploaded": False,
            "subtitle_file": str(args.output),
        }

    transcribe.set_defaults(action=action)


def main():
    run_cli("quietscribe", demo, (), extend)
