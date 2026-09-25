#!/usr/bin/env python3
"""Download and verify the model assets required by the local application.

All remote artifacts are pinned to immutable revisions and checked against
known SHA-256 digests. Re-running the script is cheap when the files are
already present and valid.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

SENTIMENT_REPO = "AtsushiHatake/ai-agent-sme-sentiment-mbert"
SENTIMENT_REVISION = "5c7888401e6bd8b1b616817f211de6348e70165d"
SENTIMENT_FILES = {
    "config.json": "1051f864b1773d65299ddd9c868bd5f72e2ffc0b470475c6fe0d905e02adbf98",
    "model.safetensors": "4f731bdebcd0f5e286c13e3944455529a070dd483fdae32eb44f61d514f147ff",
    "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
    "tokenizer.json": "2559494e39f3b9db569650f75dd5cee79571a63950be9f4d52bafb453fe6e793",
    "tokenizer_config.json": "1c441dfe412d9d7e47c960029a48a0159c23a38a9ab41b465d90fb1f520d4ced",
    "vocab.txt": "fe0fda7c425b48c516fc8f160d594c8022a0808447475c1a7c6d6479763f310c",
}

WHISPER_REPO = "Systran/faster-whisper-small"
WHISPER_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
WHISPER_FILES = {
    "config.json": "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
    "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
    "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
    "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
}

POPULARITY_REVISION = "5522ccbe8f82e352f50f39aa02921b7732de6bf6"
POPULARITY_URL = (
    "https://raw.githubusercontent.com/dingkeyan93/"
    f"Intrinsic-Image-Popularity/{POPULARITY_REVISION}/model/model-resnet50.pth"
)
POPULARITY_SHA256 = "2b43c375ff8e75856aba1d4bbe713aa6b7f4d8fcce83c0f30e6558cb6d1d783f"

DEFAULT_SENTIMENT_DIR = REPO_ROOT / "backend/data/models/sentiment-mbert"
DEFAULT_WHISPER_DIR = REPO_ROOT / "backend/data/models/faster-whisper-small"
DEFAULT_POPULARITY_FILE = (
    REPO_ROOT / "backend/data/models/popularity-resnet50/model-resnet50.pth"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid(path: Path, expected_sha256: str) -> bool:
    return path.is_file() and sha256_file(path) == expected_sha256


def sentiment_is_ready(target_dir: Path) -> bool:
    return all(
        is_valid(target_dir / filename, digest)
        for filename, digest in SENTIMENT_FILES.items()
    )


def whisper_is_ready(target_dir: Path) -> bool:
    return all(
        is_valid(target_dir / filename, digest)
        for filename, digest in WHISPER_FILES.items()
    )


def popularity_is_ready(target_file: Path) -> bool:
    return is_valid(target_file, POPULARITY_SHA256)


def download_sentiment(target_dir: Path) -> None:
    if sentiment_is_ready(target_dir):
        print(f"✓ sentiment model verified: {target_dir}")
        return

    from huggingface_hub import hf_hub_download

    target_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"▶ downloading sentiment model {SENTIMENT_REPO} "
        f"at {SENTIMENT_REVISION[:12]}…"
    )
    for filename, expected_sha256 in SENTIMENT_FILES.items():
        destination = target_dir / filename
        if destination.exists() and not is_valid(destination, expected_sha256):
            destination.unlink()
        hf_hub_download(
            repo_id=SENTIMENT_REPO,
            filename=filename,
            revision=SENTIMENT_REVISION,
            local_dir=target_dir,
        )
        if not is_valid(destination, expected_sha256):
            raise RuntimeError(f"checksum verification failed: {destination}")
    print(f"✓ sentiment model downloaded and verified: {target_dir}")


def download_whisper(target_dir: Path) -> None:
    if whisper_is_ready(target_dir):
        print(f"✓ faster-whisper model verified: {target_dir}")
        return

    from huggingface_hub import hf_hub_download

    target_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"▶ downloading faster-whisper model {WHISPER_REPO} "
        f"at {WHISPER_REVISION[:12]}…"
    )
    for filename, expected_sha256 in WHISPER_FILES.items():
        destination = target_dir / filename
        if destination.exists() and not is_valid(destination, expected_sha256):
            destination.unlink()
        hf_hub_download(
            repo_id=WHISPER_REPO,
            filename=filename,
            revision=WHISPER_REVISION,
            local_dir=target_dir,
        )
        if not is_valid(destination, expected_sha256):
            raise RuntimeError(f"checksum verification failed: {destination}")
    print(f"✓ faster-whisper model downloaded and verified: {target_dir}")


def download_popularity(target_file: Path) -> None:
    if popularity_is_ready(target_file):
        print(f"✓ popularity model verified: {target_file}")
        return

    import requests

    target_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_file.with_suffix(target_file.suffix + ".part")
    print(f"▶ downloading popularity model at {POPULARITY_REVISION[:12]}…")
    try:
        with requests.get(POPULARITY_URL, stream=True, timeout=(10, 300)) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        stream.write(chunk)
        if not is_valid(temporary, POPULARITY_SHA256):
            raise RuntimeError(f"checksum verification failed: {temporary}")
        temporary.replace(target_file)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"✓ popularity model downloaded and verified: {target_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only; do not download")
    parser.add_argument("--sentiment-dir", type=Path, default=DEFAULT_SENTIMENT_DIR)
    parser.add_argument("--whisper-dir", type=Path, default=DEFAULT_WHISPER_DIR)
    parser.add_argument("--popularity-file", type=Path, default=DEFAULT_POPULARITY_FILE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        sentiment_ready = sentiment_is_ready(args.sentiment_dir)
        whisper_ready = whisper_is_ready(args.whisper_dir)
        popularity_ready = popularity_is_ready(args.popularity_file)
        print(f"sentiment model: {'ready' if sentiment_ready else 'missing or invalid'}")
        print(f"faster-whisper model: {'ready' if whisper_ready else 'missing or invalid'}")
        print(f"popularity model: {'ready' if popularity_ready else 'missing or invalid'}")
        return 0 if sentiment_ready and whisper_ready and popularity_ready else 1

    download_sentiment(args.sentiment_dir)
    download_whisper(args.whisper_dir)
    download_popularity(args.popularity_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
