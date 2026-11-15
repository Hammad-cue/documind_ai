"""
Inference hook for the fine-tuned clause classifier (trained with ml/train_clause_classifier.py).
If no trained model exists at CLAUSE_MODEL_DIR the system simply skips clause labelling.
"""
import threading

from django.conf import settings

_pipe = None
_loaded = False
_lock = threading.Lock()


def _get_pipeline():
    global _pipe, _loaded
    if not _loaded:
        with _lock:
            if not _loaded:
                model_dir = settings.CLAUSE_MODEL_DIR
                if model_dir.exists() and (model_dir / 'config.json').exists():
                    from transformers import pipeline
                    _pipe = pipeline('text-classification', model=str(model_dir), tokenizer=str(model_dir),
                                     truncation=True, max_length=512, device=-1)
                _loaded = True
    return _pipe


def is_available():
    return _get_pipeline() is not None


def classify(texts, min_confidence=0.5):
    """Returns [(label, score)] or [(None, None)] when the model is unavailable / unsure."""
    pipe = _get_pipeline()
    if pipe is None or not texts:
        return [(None, None)] * len(texts)
    out = []
    for pred in pipe(texts, batch_size=16):
        if pred['score'] >= min_confidence:
            out.append((pred['label'], float(pred['score'])))
        else:
            out.append((None, float(pred['score'])))
    return out
