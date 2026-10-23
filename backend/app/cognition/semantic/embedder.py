"""A small sentence-embedding model, so HARIKA can compare requests by meaning.

all-MiniLM-L6-v2 (quantized, about 23 MB) runs on the CPU with onnxruntime in a few
milliseconds. It turns a sentence into a vector; sentences that mean similar things
("take a screenshot", "grab what's on my screen") get similar vectors even when they
share no words. Downloaded once into the models folder; until it is there (or if it
can't load) callers get None and use word matching instead.
"""
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.core.paths import data_path

logger = logging.getLogger("harika.semantic.embedder")

_SOURCE = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main"
_FILES = {"model_quantized.onnx": "onnx/model_quantized.onnx", "tokenizer.json": "tokenizer.json"}
_MIN_MODEL_BYTES = 10_000_000  # a cut-off download is never loaded


class Embedder:
    def __init__(self, folder: Optional[Path] = None):
        self.folder = folder or data_path("models", "minilm")
        self._session = None
        self._tokenizer = None
        self._failed = False
        self._lock = threading.Lock()
        self._cache: Dict[str, np.ndarray] = {}

    def present(self) -> bool:
        model = self.folder / "model_quantized.onnx"
        return model.exists() and model.stat().st_size > _MIN_MODEL_BYTES and (self.folder / "tokenizer.json").exists()

    def _load(self) -> bool:
        if self._session is not None:
            return True
        if self._failed or not self.present():
            return False
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            tokenizer = Tokenizer.from_file(str(self.folder / "tokenizer.json"))
            tokenizer.enable_padding()
            tokenizer.enable_truncation(128)
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            self._session = ort.InferenceSession(str(self.folder / "model_quantized.onnx"), options,
                                                 providers=["CPUExecutionProvider"])
            self._tokenizer = tokenizer
            logger.info("[Embedder] Meaning model loaded.")
            return True
        except Exception as exc:
            self._failed = True  # word matching is used instead; never retried in a loop
            logger.warning(f"[Embedder] Meaning model unavailable: {exc}")
            return False

    def embed(self, texts: List[str]) -> Optional[np.ndarray]:
        """Unit vectors, one row per text; None when the model isn't available."""
        with self._lock:
            if not self._load():
                return None
            missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
            if missing:
                encoded = self._tokenizer.encode_batch(missing)
                ids = np.array([e.ids for e in encoded], dtype=np.int64)
                mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
                feed = {"input_ids": ids, "attention_mask": mask}
                if "token_type_ids" in {i.name for i in self._session.get_inputs()}:
                    feed["token_type_ids"] = np.zeros_like(ids)
                hidden = self._session.run(None, feed)[0]
                pooled = (hidden * mask[..., None]).sum(axis=1) / np.maximum(mask.sum(axis=1, keepdims=True), 1)
                pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
                for text, vector in zip(missing, pooled):
                    self._cache[text] = vector.astype(np.float32)
                if len(self._cache) > 5000:
                    self._cache = dict(list(self._cache.items())[-2000:])
            return np.stack([self._cache[t] for t in texts])

    def download(self) -> bool:
        """Fetch the model once (blocking); True when it is ready."""
        if self.present():
            return True
        import httpx

        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            for name, remote in _FILES.items():
                partial = self.folder / f"{name}.part"
                with httpx.stream("GET", f"{_SOURCE}/{remote}", follow_redirects=True, timeout=60.0) as response:
                    response.raise_for_status()
                    with open(partial, "wb") as handle:
                        for chunk in response.iter_bytes():
                            handle.write(chunk)
                partial.replace(self.folder / name)
            logger.info("[Embedder] Meaning model downloaded.")
            return self.present()
        except Exception as exc:
            logger.warning(f"[Embedder] Download failed (word matching is used meanwhile): {exc}")
            return False


embedder = Embedder()
