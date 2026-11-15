"""
Fine-tune a transformer to classify contract clauses (the ML contribution of the project).

Dataset : LEDGAR (part of LexGLUE) — ~80k contract provisions from SEC filings, 100 clause types
          (Governing Laws, Terminations, Confidentiality, Indemnifications, ...).
Model   : nlpaueb/legal-bert-small-uncased by default (fast); try microsoft/deberta-v3-base for accuracy.
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
import json
import os
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='nlpaueb/legal-bert-small-uncased')
    p.add_argument('--epochs', type=float, default=3)
    p.add_argument('--lr', type=float, default=5e-5)
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--max-length', type=int, default=256)
    p.add_argument('--train-limit', type=int, default=0, help='use only N training examples (0 = all)')
    p.add_argument('--eval-limit', type=int, default=0, help='use only N validation/test examples (0 = all)')
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

    train, val, test = limit('train', args.train_limit), limit('validation', args.eval_limit), limit('test', args.eval_limit)
    print(f'train={len(train)} val={len(val)} test={len(test)} labels={len(label_names)}')

    tok = AutoTokenizer.from_pretrained(args.model)
    enc = lambda b: tok(b['text'], truncation=True, max_length=args.max_length)
    train, val, test = (d.map(enc, batched=True, remove_columns=['text']) for d in (train, val, test))

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(label_names),
        id2label=dict(enumerate(label_names)), label2id={n: i for i, n in enumerate(label_names)})

    def metrics(pred):
        y = pred.label_ids
        p = np.argmax(pred.predictions, axis=-1)
        return {'accuracy': accuracy_score(y, p), 'macro_f1': f1_score(y, p, average='macro'),
                'micro_f1': f1_score(y, p, average='micro')}

    run_dir = ROOT / 'runs' / time.strftime('%Y%m%d-%H%M%S')
    targs = TrainingArguments(
        output_dir=str(run_dir / 'checkpoints'), num_train_epochs=args.epochs, learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size * 2,
        eval_strategy='epoch', save_strategy='epoch', load_best_model_at_end=True, metric_for_best_model='macro_f1',
        save_total_limit=1, warmup_ratio=0.06, weight_decay=0.01, logging_steps=50, report_to=[],
        fp16=__import__('torch').cuda.is_available(), seed=args.seed)
    trainer = Trainer(model=model, args=targs, train_dataset=train, eval_dataset=val, processing_class=tok,
                      data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics)

    started = time.time()
    trainer.train()
    train_minutes = (time.time() - started) / 60

    out = trainer.predict(test)
    preds = np.argmax(out.predictions, axis=-1)
    report = classification_report(out.label_ids, preds, labels=list(range(len(label_names))),
                                   target_names=label_names, output_dict=True, zero_division=0)
    result = {'model': args.model, 'train_examples': len(train), 'test_examples': len(test), 'epochs': args.epochs,
              'train_minutes': round(train_minutes, 1), **{k.replace('test_', ''): v for k, v in out.metrics.items()},
              'per_class': {k: v for k, v in report.items() if k in label_names}}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'per_class'}, indent=2))

    os.makedirs(args.out, exist_ok=True)
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print(f'Saved model to {args.out}. Copy this folder into the project at ml/models/clause-classifier/.')


if __name__ == '__main__':
    main()
