"""
Combine the fine-tuned clause model with a TF-IDF + logistic-regression model (a weighted average of their
predicted probabilities). The two make different mistakes: TF-IDF keys on exact wording, the transformer on
meaning, so the average is usually better than either one alone.

The mixing weight is chosen on the validation split only; the test split is used once, for the final numbers.

    python ml/train_ensemble.py                    # needs ml/models/clause-classifier (the fine-tuned model)

Writes ml/models/clause-classifier/tfidf.joblib and ensemble.json (the app then uses the ensemble
automatically) and ml/runs/ensemble-<timestamp>.json with the test results.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def transformer_probs(model_dir, texts, batch_size=64, max_length=256):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            enc = tok(texts[i:i + batch_size], truncation=True, max_length=max_length, padding=True, return_tensors='pt')
            out.append(torch.softmax(model(**enc).logits, dim=-1).numpy())
            if (i // batch_size) % 25 == 0:
                print(f'  transformer {i + len(out[-1])}/{len(texts)}', flush=True)
    return np.concatenate(out)


def scores(y, p):
    from sklearn.metrics import accuracy_score, f1_score
    return {'accuracy': round(accuracy_score(y, p), 4), 'macro_f1': round(f1_score(y, p, average='macro'), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default=str(ROOT / 'models' / 'clause-classifier'))
    args = ap.parse_args()
    model_dir = Path(args.model_dir)

    import joblib
    from datasets import load_dataset
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    ds = load_dataset('coastalcph/lex_glue', 'ledgar')
    train, val, test = ds['train'], ds['validation'], ds['test']
    names = train.features['label'].names
    config = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
    id2label = {int(k): v for k, v in config['id2label'].items()}
    assert [id2label[i] for i in range(len(names))] == names, 'model labels do not match the dataset label order'

    started = time.time()
    print('training TF-IDF + logistic regression on', len(train), 'clauses', flush=True)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000, sublinear_tf=True, dtype=np.float32)
    clf = LogisticRegression(max_iter=2000, C=10).fit(vec.fit_transform(train['text']), train['label'])
    p_tfidf_val, p_tfidf_test = clf.predict_proba(vec.transform(val['text'])), clf.predict_proba(vec.transform(test['text']))

    print('scoring with the fine-tuned transformer', flush=True)
    p_bert_val = transformer_probs(model_dir, val['text'])
    p_bert_test = transformer_probs(model_dir, test['text'])

    # choose the weight of the transformer on the validation split
    from sklearn.metrics import f1_score
    y_val, y_test = np.array(val['label']), np.array(test['label'])
    grid = [round(w, 2) for w in np.arange(0, 1.01, 0.05)]
    val_f1 = {w: f1_score(y_val, (w * p_bert_val + (1 - w) * p_tfidf_val).argmax(1), average='macro') for w in grid}
    w = max(val_f1, key=val_f1.get)
    print(f'best transformer weight on validation: {w} (macro-F1 {val_f1[w]:.4f})', flush=True)

    result = {
        'train_examples': len(train), 'validation_examples': len(val), 'test_examples': len(test),
        'transformer_weight': w, 'minutes': round((time.time() - started) / 60, 1),
        'validation_macro_f1_by_weight': {str(k): round(v, 4) for k, v in val_f1.items()},
        'test': {
            'tfidf': scores(y_test, p_tfidf_test.argmax(1)),
            'transformer': scores(y_test, p_bert_test.argmax(1)),
            'ensemble': scores(y_test, (w * p_bert_test + (1 - w) * p_tfidf_test).argmax(1)),
        },
    }
    clf.coef_ = clf.coef_.astype(np.float32)        # halves the file size, no measurable effect on accuracy
    joblib.dump({'vectorizer': vec, 'classifier': clf}, model_dir / 'tfidf.joblib', compress=3)
    (model_dir / 'ensemble.json').write_text(json.dumps({'transformer_weight': w, 'tfidf_file': 'tfidf.joblib'}, indent=2))
    out = ROOT / 'runs' / f'ensemble-{time.strftime("%Y%m%d-%H%M%S")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result['test'], indent=2), f'\nsaved {out}')


if __name__ == '__main__':
    main()
