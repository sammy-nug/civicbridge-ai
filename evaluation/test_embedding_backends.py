"""Check that the two embedding runtimes agree, since we may index with one and serve with the other.

Run: cd backend && .venv/bin/python -m pytest ../evaluation/test_embedding_backends.py -v
"""
import numpy as np
import pytest

pytest.importorskip("sentence_transformers")

from app.services.embeddings import OnnxEmbedder, SentenceTransformerEmbedder  # noqa: E402

TEXTS = [
    "How can I replace a lost PVC?",
    "Whenever a voter's card is lost, destroyed, defaced, torn or otherwise damaged, the owner shall apply in person.",
    "Polling units open nationwide at 8:30 AM.",
    "Ta yaya zan yi rajistar zaɓe?",
]


def test_backends_produce_matching_vectors():
    first = np.array(SentenceTransformerEmbedder().embed(TEXTS))
    second = np.array(OnnxEmbedder().embed(TEXTS))
    assert first.shape == second.shape == (len(TEXTS), 384)
    cosine = (first * second).sum(axis=1)
    print("cosine per text:", cosine.round(5).tolist())
    assert cosine.min() > 0.99
