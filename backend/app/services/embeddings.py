"""Text embeddings, switchable between two runtimes of the same model (all-MiniLM-L6-v2).

  sentence_transformers  the reference implementation; needs PyTorch (about 1.5 GB installed).
  onnx                   ChromaDB's bundled ONNX build; no PyTorch, so it fits on small hosts.

evaluation/test_embedding_backends.py checks that the two produce matching vectors, which
is what lets us index with one and serve with the other.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

import numpy as np

from app.config import get_settings

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _unit_length(vectors: np.ndarray) -> list[list[float]]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.clip(norms, 1e-12, None)).tolist()


class SentenceTransformerEmbedder:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(MODEL_NAME, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return _unit_length(np.asarray(self._model.encode(texts, batch_size=32, show_progress_bar=False)))


class OnnxEmbedder:
    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        # Keep the model beside the index. Hosts may discard ~/.cache after the build step.
        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = get_settings().data_dir / "onnx_models" / ONNXMiniLM_L6_V2.MODEL_NAME
        self._model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])

    def embed(self, texts: list[str]) -> list[list[float]]:
        return _unit_length(np.asarray(self._model(texts)))


@lru_cache
def get_embedder() -> Embedder:
    backend = get_settings().embedding_backend
    if backend == "sentence_transformers":
        return SentenceTransformerEmbedder()
    if backend == "onnx":
        return OnnxEmbedder()
    raise ValueError(f"Unknown EMBEDDING_BACKEND '{backend}'. Use 'onnx' or 'sentence_transformers'.")
