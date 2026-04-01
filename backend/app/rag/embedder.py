"""
AIS NVIDIA NIM Embedding Client
Uses NVIDIA's llama-nemotron-embed-1b-v2 via OpenAI-compatible API.

Model specs:
- 2048-dimensional embeddings
- 8192 token context window
- 26 language support
- Asymmetric retrieval: separate query/passage input types
- Endpoint: https://integrate.api.nvidia.com/v1
"""
from __future__ import annotations

import asyncio
from typing import List, Literal
from openai import OpenAI, AsyncOpenAI
from loguru import logger

from app.core.config import settings


class NVIDIAEmbedder:
    """
    NVIDIA NIM embedding client using llama-nemotron-embed-1b-v2.
    Supports asymmetric query/passage embedding for accurate retrieval.
    """

    def __init__(self):
        self._sync_client = OpenAI(
            base_url=settings.NVIDIA_NIM_BASE_URL,
            api_key=settings.NVIDIA_EMBED_API_KEY,
        )
        self._async_client = AsyncOpenAI(
            base_url=settings.NVIDIA_NIM_BASE_URL,
            api_key=settings.NVIDIA_EMBED_API_KEY,
        )
        self.model = settings.NVIDIA_EMBED_MODEL
        self.dimension = 2048
        logger.info(f"NVIDIAEmbedder initialized: model={self.model}")

    def embed_passages(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Embed document passages (for indexing into Weaviate).
        Uses input_type='passage' for asymmetric retrieval.
        """
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self._sync_client.embeddings.create(
                input=batch,
                model=self.model,
                encoding_format="float",
                extra_body={
                    "input_type": "passage",
                    "truncate": "END",
                }
            )
            batch_embeddings = [r.embedding for r in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)
            logger.debug(f"Embedded passage batch {i//batch_size + 1}: {len(batch)} texts")
        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a user query (for retrieval).
        Uses input_type='query' for asymmetric retrieval.
        """
        response = self._sync_client.embeddings.create(
            input=[query],
            model=self.model,
            encoding_format="float",
            extra_body={
                "input_type": "query",
                "truncate": "END",
            }
        )
        return response.data[0].embedding

    async def embed_passages_async(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Async version for passage embedding."""
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self._async_client.embeddings.create(
                input=batch,
                model=self.model,
                encoding_format="float",
                extra_body={"input_type": "passage", "truncate": "END"}
            )
            batch_embeddings = [r.embedding for r in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)
        return all_embeddings

    async def embed_query_async(self, query: str) -> List[float]:
        """Async version for query embedding."""
        response = await self._async_client.embeddings.create(
            input=[query],
            model=self.model,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"}
        )
        return response.data[0].embedding

    def embed_multiple_queries(self, queries: List[str]) -> List[List[float]]:
        """Embed multiple sub-queries for multi-query retrieval."""
        return self.embed_passages(queries)  # queries as passages for multi-query


# Module-level singleton
_embedder: NVIDIAEmbedder | None = None


def get_embedder() -> NVIDIAEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = NVIDIAEmbedder()
    return _embedder
