"""Singleton wrapper around a local llama.cpp model."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger("bookforge.llm.engine")

# HuggingFace repo + file for the instruction-tuned model.
# Q4_K_M quantisation, ~2GB on disk, fits comfortably on a 12GB GPU
# alongside XTTS v2 (which uses ~2-3GB when loaded).
MODEL_REPO = "bartowski/Qwen2.5-3B-Instruct-GGUF"
MODEL_FILE = "Qwen2.5-3B-Instruct-Q4_K_M.gguf"

# Where the model is cached. In the container, /models is a persistent volume.
MODEL_CACHE_DIR = Path("/models/llm") if Path("/models").exists() else Path.home() / ".cache" / "bookforge" / "llm"


class LLMEngine:
    """Loads and caches a single llama.cpp model instance.

    Not thread-safe for concurrent inference — callers should serialize.
    Model loading is lazy: the constructor only records intent; the model
    is fetched and loaded on the first call to generate().
    """

    def __init__(
        self,
        repo_id: str = MODEL_REPO,
        filename: str = MODEL_FILE,
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
    ) -> None:
        self._repo_id = repo_id
        self._filename = filename
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = n_ctx
        self._llm = None
        self._load_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def _ensure_loaded(self) -> None:
        if self._llm is not None:
            return
        with self._load_lock:
            if self._llm is not None:
                return
            from llama_cpp import Llama

            MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Loading LLM: {self._repo_id}/{self._filename}")
            self._llm = Llama.from_pretrained(
                repo_id=self._repo_id,
                filename=self._filename,
                n_gpu_layers=self._n_gpu_layers,
                n_ctx=self._n_ctx,
                verbose=False,
            )
            logger.info("LLM loaded.")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> str:
        """Run inference and return the model's text response.

        When response_format is {"type": "json_object"}, llama-cpp-python
        constrains generation to produce valid JSON.
        """
        self._ensure_loaded()
        assert self._llm is not None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        response = self._llm.create_chat_completion(**kwargs)
        return response["choices"][0]["message"]["content"]


_engine: LLMEngine | None = None


def get_engine() -> LLMEngine:
    """Return the process-wide singleton engine, creating it if needed."""
    global _engine
    if _engine is None:
        _engine = LLMEngine()
    return _engine