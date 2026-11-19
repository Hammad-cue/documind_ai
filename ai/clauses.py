"""
Inference hook for the clause classifier.

  - ml/models/clause-classifier/            the fine-tuned transformer (ml/train_clause_classifier.py)
  - .../tfidf.joblib + ensemble.json        optional TF-IDF model and mixing weight (ml/train_ensemble.py)

When the ensemble files are present, the label is the arg-max of a weighted average of both models'
probabilities; otherwise the transformer alone is used. Without a trained model, clause labelling is skipped.
"""
import json
import threading

from django.conf import settings

_state = {'loaded': False, 'pipe': None, 'tfidf': None, 'weight': 1.0, 'label2id': None}
_lock = threading.Lock()


def _load():
    if _state['loaded']:
        return _state
    with _lock:
        if _state['loaded']:
            return _state
        model_dir = settings.CLAUSE_MODEL_DIR
        if model_dir.exists() and (model_dir / 'config.json').exists():
            from transformers import pipeline
            pipe = pipeline('text-classification', model=str(model_dir), tokenizer=str(model_dir),
                            truncation=True, max_length=512, device=-1)
            _state['pipe'] = pipe
            _state['label2id'] = pipe.model.config.label2id
            ens = model_dir / 'ensemble.json'
            if ens.exists():
                try:
                    import joblib
                    cfg = json.loads(ens.read_text(encoding='utf-8'))
                    _state['tfidf'] = joblib.load(model_dir / cfg.get('tfidf_file', 'tfidf.joblib'))
                    _state['weight'] = float(cfg['transformer_weight'])
                except Exception:      # a broken ensemble file must not stop document processing
                    _state['tfidf'] = None
        _state['loaded'] = True
    return _state


def is_available():
    return _load()['pipe'] is not None


def mode():
    s = _load()
    if s['pipe'] is None:
        return None
    return 'ensemble' if s['tfidf'] is not None else 'transformer'


def classify(texts, min_confidence=0.5):
    """Returns [(label, score)] or [(None, score)] when unsure, [(None, None)] when no model is available."""
    s = _load()
    pipe = s['pipe']
    if pipe is None or not texts:
        return [(None, None)] * len(texts)

    if s['tfidf'] is None:
        preds = [(p['label'], float(p['score'])) for p in pipe(texts, batch_size=16)]
    else:
        import numpy as np
        n_labels = len(s['label2id'])
        p_bert = np.zeros((len(texts), n_labels), dtype=np.float32)
        for row, scores in enumerate(pipe(texts, batch_size=16, top_k=None)):
            for item in scores:
                p_bert[row, s['label2id'][item['label']]] = item['score']
        vec, clf = s['tfidf']['vectorizer'], s['tfidf']['classifier']
        p_tfidf = np.zeros_like(p_bert)
        p_tfidf[:, clf.classes_] = clf.predict_proba(vec.transform(texts))
        p = s['weight'] * p_bert + (1 - s['weight']) * p_tfidf
        id2label = {i: label for label, i in s['label2id'].items()}
        preds = [(id2label[int(i)], float(p[r, i])) for r, i in enumerate(p.argmax(1))]

    return [(label, score) if score >= min_confidence else (None, score) for label, score in preds]
