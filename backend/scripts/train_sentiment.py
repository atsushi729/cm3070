"""Fine-tune multilingual BERT for UC2 sentiment.

Fine-tunes settings.sentiment_finetune_base (bert-base-multilingual-cased) on the
synthetic train split and saves to settings.sentiment_model_path. id2label is set
to app.ai.sentiment.LABELS so the saved model (and the transformers pipeline that
loads it) emits canonical labels directly.

Run from backend/ (venv active; first run downloads the base model once):
    python -m scripts.train_sentiment --epochs 4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ai.sentiment import LABELS
from app.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TRAIN = _REPO_ROOT / "data" / "testset" / "sentiment_train.json"


def read_split(path: Path) -> tuple[list[str], list[int]]:
    """Load a sentiment split into parallel texts and integer label ids."""
    data = json.loads(Path(path).read_text())
    texts = [it["text"] for it in data["items"]]
    ids = [LABELS.index(it["label"]) for it in data["items"]]
    return texts, ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", type=Path, default=_DEFAULT_TRAIN)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None, help="use first N examples (smoke test)")
    args = ap.parse_args()

    import torch
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              Trainer, TrainingArguments)

    settings = get_settings()
    texts, ids = read_split(args.train)
    if args.limit:
        texts, ids = texts[: args.limit], ids[: args.limit]

    tok = AutoTokenizer.from_pretrained(settings.sentiment_finetune_base)
    enc = tok(texts, truncation=True, max_length=128, padding=True)

    class _DS(torch.utils.data.Dataset):
        def __len__(self): return len(ids)
        def __getitem__(self, i):
            item = {k: torch.tensor(v[i]) for k, v in enc.items()}
            item["labels"] = torch.tensor(ids[i])
            return item

    model = AutoModelForSequenceClassification.from_pretrained(
        settings.sentiment_finetune_base,
        num_labels=len(LABELS),
        id2label={i: l for i, l in enumerate(LABELS)},
        label2id={l: i for i, l in enumerate(LABELS)},
    )

    out_dir = _REPO_ROOT / "backend" / settings.sentiment_model_path
    targs = TrainingArguments(
        output_dir=str(out_dir / "_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        learning_rate=args.lr,
        logging_steps=10,
        save_strategy="no",
        report_to=[],
    )
    Trainer(model=model, args=targs, train_dataset=_DS()).train()

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print(f"Saved fine-tuned sentiment model -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
