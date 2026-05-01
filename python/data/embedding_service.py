"""
Embedding Service for Semantic Search

Provides text embeddings using sentence-transformers for semantic bubble/idea search.
Uses Qwen/Qwen3-Embedding-0.6B model (1024 dimensions, multilingual DE/EN).
"""

import json
import os
import hashlib
import logging
import threading
from typing import List, Optional, Tuple
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)

# System Status Monitor integration
try:
    from swarm.monitoring.system_status import get_status_monitor
    _monitor = get_status_monitor()
except ImportError:
    _monitor = None

# Thread-safe lazy-loaded model instance
_model = None
_model_lock = threading.Lock()
_model_load_attempted = False


def _get_model():
    """Lazy-load the sentence-transformers model with timeout and monitoring.

    Thread-safe: uses a lock so concurrent callers wait for loading to complete
    rather than falling back to hash-based embeddings.
    """
    global _model, _model_load_attempted

    if _model is not None:
        return _model

    with _model_lock:
        # Double-check after acquiring lock
        if _model is not None:
            return _model

        if _model_load_attempted:
            return None

        _model_load_attempted = True
        op_id = None

        try:
            from sentence_transformers import SentenceTransformer

            # Start monitoring
            if _monitor:
                op_id = _monitor.start_operation(
                    "model_load",
                    "Loading embedding model Qwen/Qwen3-Embedding-0.6B",
                    {"model": "Qwen/Qwen3-Embedding-0.6B"}
                )

            _logger.debug("[EmbeddingService] Loading model Qwen/Qwen3-Embedding-0.6B...")
            logger.info("[EmbeddingService] Loading model Qwen/Qwen3-Embedding-0.6B...")

            # Load with timeout (60 seconds max)
            def load_model():
                return SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(load_model)
                try:
                    _model = future.result(timeout=60)
                except FuturesTimeoutError:
                    _model_load_attempted = False  # Allow retry
                    logger.error("[EmbeddingService] Model loading timed out after 60s")
                    _logger.debug("[EmbeddingService] Model loading TIMEOUT (60s)")
                    if _monitor and op_id:
                        _monitor.complete_operation(op_id, success=False, error="Timeout after 60s")
                    return None

            _logger.debug("[EmbeddingService] Model loaded successfully")
            logger.info("[EmbeddingService] Model loaded successfully")

            if _monitor and op_id:
                _monitor.complete_operation(op_id, success=True)

            return _model

        except ImportError:
            logger.warning("[EmbeddingService] sentence-transformers not installed. "
                          "Run: pip install sentence-transformers")
            _logger.debug("[EmbeddingService] sentence-transformers NOT INSTALLED")
            if _monitor and op_id:
                _monitor.complete_operation(op_id, success=False, error="Not installed")
            return None
        except Exception as e:
            _model_load_attempted = False  # Allow retry on transient errors
            logger.error(f"[EmbeddingService] Failed to load model: {e}")
            _logger.debug(f"[EmbeddingService] FAILED: {e}")
            if _monitor and op_id:
                _monitor.complete_operation(op_id, success=False, error=str(e))
            return None


class HashBasedEmbedding:
    """
    Fallback embedding using hash-based vectors.

    Creates deterministic embeddings based on text content.
    Not as good as real embeddings but works for basic similarity.
    """

    EMBEDDING_DIM = 1024

    def encode(self, texts, convert_to_numpy=True):
        """Generate hash-based embeddings for texts."""
        import numpy as np

        if isinstance(texts, str):
            texts = [texts]

        embeddings = []
        for text in texts:
            embedding = self._text_to_vector(text)
            embeddings.append(embedding)

        result = np.array(embeddings)
        return result

    def _text_to_vector(self, text: str) -> List[float]:
        """Convert text to a hash-based vector."""
        import hashlib
        import math

        if not text:
            return [0.0] * self.EMBEDDING_DIM

        # Normalize text
        text = text.strip().lower()

        # Create base hash
        base_hash = hashlib.sha256(text.encode('utf-8')).digest()

        # Generate embedding from hash + word hashes
        vector = []

        # Use hash bytes for first part
        for i in range(min(32, self.EMBEDDING_DIM)):
            vector.append((base_hash[i % 32] / 255.0) - 0.5)

        # Generate rest from word hashes
        words = text.split()
        for i in range(32, self.EMBEDDING_DIM):
            word_idx = i % max(1, len(words))
            word = words[word_idx] if words else ""
            word_hash = hashlib.md5(f"{word}_{i}".encode()).digest()
            value = (word_hash[i % 16] / 255.0) - 0.5
            vector.append(value)

        # Normalize vector
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector


class EmbeddingService:
    """
    Service for generating and comparing text embeddings.

    Uses sentence-transformers Qwen/Qwen3-Embedding-0.6B model:
    - 1024 dimensions
    - GPU-friendly (Qwen runs ~640 emb/s on RTX 3060)
    - Strong multilingual support (German + English)

    Falls back to hash-based embeddings if model fails to load.
    """

    EMBEDDING_DIM = 1024

    def __init__(self):
        """Initialize the embedding service."""
        self._model = None
        self._fallback_model = None
        self._using_fallback = False

    @property
    def model(self):
        """Get the model (lazy-loaded, with fallback).

        Tries to load the real model first. Only falls back to hash-based
        if the real model permanently failed (ImportError).
        """
        if self._model is None:
            self._model = _get_model()

            if self._model is not None:
                # Real model loaded — clear any previous fallback
                if self._using_fallback:
                    logger.info("[EmbeddingService] Upgraded from fallback to real model")
                    _logger.debug("[EmbeddingService] Upgraded to real model")
                    self._fallback_model = None
                    self._using_fallback = False
            elif self._fallback_model is None:
                # Use fallback if main model failed
                logger.info("[EmbeddingService] Using hash-based fallback embeddings")
                _logger.debug("[EmbeddingService] Using hash-based fallback")
                self._fallback_model = HashBasedEmbedding()
                self._using_fallback = True

        return self._model if self._model is not None else self._fallback_model

    @property
    def is_available(self) -> bool:
        """Check if the embedding service is available (including fallback)."""
        return self.model is not None

    @property
    def is_using_fallback(self) -> bool:
        """Check if using fallback embeddings."""
        return self._using_fallback

    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            List of floats (1024 dimensions native, optionally truncated to
            EMBEDDING_TARGET_DIM if set via env — used to fit Supabase's
            vector(384) column without a schema migration). None if
            service unavailable.
        """
        if not self.is_available:
            logger.debug("[EmbeddingService] Service unavailable, returning None")
            return None

        if not text or not text.strip():
            logger.debug("[EmbeddingService] Empty text, returning None")
            return None

        try:
            # Normalize text
            text = text.strip().lower()
            embedding = self.model.encode(text, convert_to_numpy=True)

            # Handle 2D array case (batch encoding returns 2D even for single text)
            result = embedding.tolist()
            if isinstance(result, list) and len(result) == 1 and isinstance(result[0], list):
                result = result[0]  # Flatten [[...]] to [...]

            # Optional truncation for storage backends with fixed-dim columns.
            # Qwen-Embedding-0.6B is 1024d, but Supabase schema uses vector(384)
            # via HNSW index — taking the leading 384 dims preserves the highest-
            # variance components and works as a pragmatic workaround for
            # similarity search without a schema migration.
            target_dim = int(os.environ.get("EMBEDDING_TARGET_DIM", "0") or 0)
            if target_dim and len(result) > target_dim:
                result = result[:target_dim]

            return result
        except Exception as e:
            logger.error(f"[EmbeddingService] Failed to embed text: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (some may be None)
        """
        if not self.is_available:
            return [None] * len(texts)

        # Filter and track empty texts
        valid_indices = []
        valid_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_indices.append(i)
                valid_texts.append(text.strip().lower())

        if not valid_texts:
            return [None] * len(texts)

        try:
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)

            # Reconstruct results with None for empty texts
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices):
                results[idx] = embeddings[i].tolist()
            return results
        except Exception as e:
            logger.error(f"[EmbeddingService] Failed to embed batch: {e}")
            return [None] * len(texts)

    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between -1 and 1 (1 = identical)
        """
        if vec1 is None or vec2 is None:
            return 0.0

        # Handle nested lists [[...]] from database or 2D arrays
        if isinstance(vec1, list) and len(vec1) == 1 and isinstance(vec1[0], list):
            vec1 = vec1[0]
        if isinstance(vec2, list) and len(vec2) == 1 and isinstance(vec2[0], list):
            vec2 = vec2[0]

        if len(vec1) != len(vec2):
            logger.warning(f"[EmbeddingService] Vector length mismatch: {len(vec1)} vs {len(vec2)}")
            return 0.0

        # Cosine similarity using numpy if available, else pure Python
        try:
            import numpy as np
            v1 = np.array(vec1).flatten()  # Ensure 1D
            v2 = np.array(vec2).flatten()  # Ensure 1D
            dot = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot / (norm1 * norm2))
        except ImportError:
            # Fallback to pure Python
            dot = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

    def find_most_similar(
        self,
        query_vec: List[float],
        candidates: List[Tuple[str, List[float]]],
        top_k: int = 5,
        min_score: float = 0.0
    ) -> List[Tuple[str, float]]:
        """
        Find most similar items from candidates.

        Args:
            query_vec: Query embedding vector
            candidates: List of (id, embedding_vector) tuples
            top_k: Number of results to return
            min_score: Minimum similarity score threshold

        Returns:
            List of (id, score) tuples sorted by similarity descending
        """
        if query_vec is None:
            return []

        scores = []
        for item_id, item_vec in candidates:
            if item_vec is not None:
                score = self.similarity(query_vec, item_vec)
                if score >= min_score:
                    scores.append((item_id, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def text_similarity(text1: str, text2: str) -> float:
        """
        Calculate text similarity using word overlap (Jaccard similarity).
        This is a fallback when embeddings are not available.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        logger.debug("text_similarity: text1_len=%s text2_len=%s", len(text1), len(text2))
        if not text1 or not text2:
            return 0.0

        # Normalize and tokenize
        import re
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))

        # Remove common stop words (German + English)
        stop_words = {
            'der', 'die', 'das', 'und', 'ist', 'in', 'von', 'mit', 'für', 'auf',
            'ein', 'eine', 'zu', 'den', 'dem', 'als', 'an', 'es', 'im', 'wird',
            'the', 'a', 'an', 'and', 'is', 'in', 'of', 'with', 'for', 'on',
            'to', 'it', 'are', 'be', 'this', 'that', 'was', 'or', 'by', 'at'
        }
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def content_hash(text: str) -> str:
        """
        Generate hash of text for change detection.

        Args:
            text: Text to hash

        Returns:
            MD5 hash of normalized text
        """
        if not text:
            return ""
        normalized = text.strip().lower()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def vector_to_json(vec: List[float]) -> str:
        """Serialize embedding vector to JSON string for storage."""
        if vec is None:
            return ""
        return json.dumps(vec)

    @staticmethod
    def vector_from_json(json_str: str) -> Optional[List[float]]:
        """Deserialize embedding vector from JSON string."""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return None


# Singleton instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
