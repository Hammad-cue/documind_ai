"""
Baselines to compare the fine-tuned clause classifier against (needed for the evaluation chapter).

  1. TF-IDF + Logistic Regression   (classic ML baseline, runs on CPU in a few minutes)
  2. Zero-shot LLM                  (the same LLM the system uses, given the label list; small sample only)

    pip install datasets scikit-learn
    python ml/baselines.py tfidf
    python ml/baselines.py llm --eval-limit 200      # needs GROQ_API_KEY; costs API calls
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(eval_limit, seed=42):
    from datasets import load_dataset
    ds = load_dataset('coastalcph/lex_glue', 'ledgar')
    test = ds['test'].shuffle(seed=seed).select(range(min(eval_limit, len(ds['test'])))) if eval_limit else ds['test']
    return ds['train'], test, ds['train'].features['label'].names


def save(name, result):
    out = ROOT / 'runs' / f'baseline-{name}-{time.strftime("%Y%m%d-%H%M%S")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), f'\nsaved {out}')


def tfidf(args):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    train, test, _ = load(args.eval_limit)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000, sublinear_tf=True)
    X = vec.fit_transform(train['text'])
    clf = LogisticRegression(max_iter=2000, C=10, n_jobs=-1).fit(X, train['label'])
    p = clf.predict(vec.transform(test['text']))
    save('tfidf', {'model': 'tfidf+logreg', 'test_examples': len(test), 'accuracy': accuracy_score(test['label'], p),
                   'macro_f1': f1_score(test['label'], p, average='macro'),
                   'micro_f1': f1_score(test['label'], p, average='micro')})


def llm_zero_shot(args):
    sys.path.insert(0, str(ROOT.parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    import django
    django.setup()
    from ai import llm
    from sklearn.metrics import accuracy_score, f1_score
    _, test, names = load(args.eval_limit or 200)
    labels = ', '.join(names)
    y, p = [], []
    for i, row in enumerate(test):
        prompt = (f'Classify this contract clause into exactly one of these categories:\n{labels}\n\n'
                  f'Clause: """{row["text"][:2000]}"""\n\nReturn JSON {{"label": "<category>"}}')
        try:
            out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=60, temperature=0)
            guess = names.index(out.get('label')) if out.get('label') in names else -1
        except Exception:
            guess = -1
        y.append(row['label'])
        p.append(guess)
        if (i + 1) % 20 == 0:
            print(f'{i + 1}/{len(test)} acc so far {accuracy_score(y, p):.3f}')
    save('llm-zero-shot', {'model': f'zero-shot {os.environ.get("LLM_MODEL", "default LLM")}', 'test_examples': len(test),
                           'accuracy': accuracy_score(y, p), 'macro_f1': f1_score(y, p, average='macro'),
                           'micro_f1': f1_score(y, p, average='micro'), 'unparseable': p.count(-1)})


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('which', choices=['tfidf', 'llm'])
    ap.add_argument('--eval-limit', type=int, default=0)
    a = ap.parse_args()
    tfidf(a) if a.which == 'tfidf' else llm_zero_shot(a)
