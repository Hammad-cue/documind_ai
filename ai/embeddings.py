"""Local sentence-embedding model (runs on CPU, no API cost). Loaded lazily once."""
import threading

from django.conf import settings

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_texts(texts, batch_size=32):
    if not texts:
        return []
    vectors = _get_model().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                                  show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text):
    return embed_texts([text])[0]
