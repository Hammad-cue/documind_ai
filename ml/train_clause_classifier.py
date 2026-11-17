"""
Fine-tune a transformer to classify contract clauses (the ML contribution of the project).

Dataset : LEDGAR (part of LexGLUE) — ~80k contract provisions from SEC filings, 100 clause types
          (Governing Laws, Terminations, Confidentiality, Indemnifications, ...).
Model   : sentence-transformers/all-MiniLM-L6-v2 by default (fast, runs on CPU at inference time).
Output  : ml/models/clause-classifier/  (the backend loads it automatically from CLAUSE_MODEL_DIR)
Metrics : accuracy, macro-F1, micro-F1 on the official test split -> ml/runs/<run>/metrics.json

Run on a free GPU (Google Colab / Kaggle):
    pip install -U transformers datasets accelerate scikit-learn
    python ml/train_clause_classifier.py --epochs 3 --train-limit 20000     # ~25 min on a T4
    python ml/train_clause_classifier.py --epochs 3                         # full data, ~1.5 h

"Smaller sets" option for quick experiments on CPU:
    python ml/train_clause_classifier.py --train-limit 3000 --eval-limit 1000 --epochs 2
"""
import argparse
import inspect
import json
import math
import os
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def training_arguments(**kwargs):
    """TrainingArguments that tolerates transformers versions: options the installed version no longer has are
    skipped (with a note) instead of crashing, because Colab always installs the newest release."""
    from transformers import TrainingArguments
    accepted = inspect.signature(TrainingArguments.__init__).parameters
    dropped = sorted(k for k in kwargs if k not in accepted)
    if dropped:
        print(f'note: this transformers version has no {", ".join(dropped)}; skipping')
    return TrainingArguments(**{k: v for k, v in kwargs.items() if k in accepted})


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='sentence-transformers/all-MiniLM-L6-v2')
    p.add_argument('--epochs', type=float, default=3)
    p.add_argument('--lr', type=float, default=5e-5)
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--max-length', type=int, default=256)
    p.add_argument('--train-limit', type=int, default=0, help='use only N training examples (0 = all)')
    p.add_argument('--eval-limit', type=int, default=0, help='use only N validation examples (0 = all)')
    p.add_argument('--test-limit', type=int, default=0, help='use only N test examples (0 = all, needed to compare with baselines)')
    p.add_argument('--out', default=str(ROOT / 'models' / 'clause-classifier'))
    p.add_argument('--seed', type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()
    from datasets import load_dataset
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, Trainer,
                              TrainingArguments, set_seed)

    set_seed(args.seed)
    ds = load_dataset('coastalcph/lex_glue', 'ledgar')
    label_names = ds['train'].features['label'].names

    def limit(split, n):
        return ds[split].shuffle(seed=args.seed).select(range(min(n, len(ds[split])))) if n else ds[split]

    train, val, test = limit('train', args.train_limit), limit('validation', args.eval_limit), limit('test', args.test_limit)
    print(f'train={len(train)} val={len(val)} test={len(test)} labels={len(label_names)}')

    tok = AutoTokenizer.from_pretrained(args.model)
    enc = lambda b: tok(b['text'], truncation=True, max_length=args.max_length)
    train, val, test = (d.map(enc, batched=True, remove_columns=['text']) for d in (train, val, test))

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=len(label_names))
    # set the clause names explicitly so the saved model reports "Governing Laws", not "LABEL_43"
    model.config.id2label = dict(enumerate(label_names))
    model.config.label2id = {n: i for i, n in enumerate(label_names)}

    def metrics(pred):
        y = pred.label_ids
        p = np.argmax(pred.predictions, axis=-1)
        return {'accuracy': accuracy_score(y, p), 'macro_f1': f1_score(y, p, average='macro'),
                'micro_f1': f1_score(y, p, average='micro')}

    run_dir = ROOT / 'runs' / time.strftime('%Y%m%d-%H%M%S')
    cuda = __import__('torch').cuda.is_available()
    # Warm up over the first 6% of steps. Given as a step count: newer transformers releases removed `warmup_ratio`.
    total_steps = math.ceil(math.ceil(len(train) / args.batch_size) * args.epochs)
    targs = training_arguments(
        output_dir=str(run_dir / 'checkpoints'), num_train_epochs=args.epochs, learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size * 2,
        dataloader_num_workers=0, use_cpu=not cuda,
        # No mid-training checkpoints: transformers 5.x on Windows reloads BERT checkpoints with mismatched
        # LayerNorm names, silently resetting those weights. We save once at the end and test the reloaded copy.
        eval_strategy='epoch', save_strategy='no', warmup_steps=max(1, round(0.06 * total_steps)), weight_decay=0.01,
        logging_steps=50, report_to=[], fp16=cuda, seed=args.seed)
    trainer = Trainer(model=model, args=targs, train_dataset=train, eval_dataset=val, processing_class=tok,
                      data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics)

    started = time.time()
    trainer.train()
    train_minutes = (time.time() - started) / 60

    # save, then reload from disk and test THAT copy, so the score is for exactly what the app will load
    os.makedirs(args.out, exist_ok=True)
    trainer.model.config.id2label = dict(enumerate(label_names))
    trainer.model.config.label2id = {n: i for i, n in enumerate(label_names)}
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    reloaded = AutoModelForSequenceClassification.from_pretrained(args.out)
    tester = Trainer(model=reloaded, args=targs, eval_dataset=val, processing_class=tok, data_collator=DataCollatorWithPadding(tok),
                     compute_metrics=metrics)
    out = tester.predict(test)
    preds = np.argmax(out.predictions, axis=-1)
    report = classification_report(out.label_ids, preds, labels=list(range(len(label_names))),
                                   target_names=label_names, output_dict=True, zero_division=0)
    result = {'model': args.model, 'train_examples': len(train), 'test_examples': len(test), 'epochs': args.epochs,
              'train_minutes': round(train_minutes, 1), **{k.replace('test_', ''): v for k, v in out.metrics.items()},
              'per_class': {k: v for k, v in report.items() if k in label_names}}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'per_class'}, indent=2))

    print(f'Saved model to {args.out} (the backend loads it from CLAUSE_MODEL_DIR).')


if __name__ == '__main__':
    main()
