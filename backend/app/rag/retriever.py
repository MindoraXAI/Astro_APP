"""
AIS retrieval pipeline with local fallback.

When Weaviate or NVIDIA embeddings are unavailable, the app falls back to a
local on-disk corpus built from curated source texts and seed knowledge.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger
import requests

from app.core.config import settings
from app.core.models import ChartState
from app.rag.seed_data.knowledge_base import ALL_SEED_DATA
from app.rag.weaviate_client import hybrid_search


SEARCH_COLLECTIONS = [
    "YogaDescription",
    "DashaEffect",
    "TransitEffect",
    "PlanetSignification",
    "HouseLordEffect",
    "HistoricalChartExample",
]

CURATED_CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]+", text.lower())


@lru_cache(maxsize=1)
def _load_local_documents() -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []

    for collection_name, items in ALL_SEED_DATA.items():
        for item in items:
            text = item.get("full_text", "").strip()
            if not text:
                continue
            documents.append(
                {
                    "text": text,
                    "source_ref": item.get("source_ref") or item.get("source") or collection_name,
                    "collection": collection_name,
                }
            )

    if CURATED_CORPUS_DIR.exists():
        for corpus_path in CURATED_CORPUS_DIR.glob("*.jsonl"):
            with corpus_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = record.get("text", "").strip()
                    if not text:
                        continue
                    documents.append(
                        {
                            "text": text,
                            "source_ref": record.get("source_id", corpus_path.stem),
                            "collection": "CuratedCorpus",
                        }
                    )

    logger.info(f"Loaded {len(documents)} local retrieval documents")
    return documents


class RAGRetriever:
    """Hybrid retrieval with local fallback."""

    def __init__(self):
        self.enable_remote = bool(settings.NVIDIA_EMBED_API_KEY) and self._remote_services_ready()
        self.embedder = None
        if self.enable_remote:
            try:
                from app.rag.embedder import get_embedder

                self.embedder = get_embedder()
            except Exception as exc:
                logger.warning(f"Remote embedder unavailable, using local retrieval only: {exc}")
                self.enable_remote = False

    def _remote_services_ready(self) -> bool:
        try:
            ready_url = f"{settings.WEAVIATE_URL.rstrip('/')}/v1/.well-known/ready"
            response = requests.get(ready_url, timeout=2)
            return response.ok
        except Exception:
            return False

    def formulate_queries(
        self,
        user_query: str,
        chart: ChartState,
        life_domain: str = "general",
    ) -> List[str]:
        cd = chart.current_dasha
        queries = [
            f"{life_domain} {user_query}",
            f"{cd.mahadasha} mahadasha {cd.antardasha} antardasha {life_domain} effects",
            f"{chart.lagna} ascendant {chart.moon_sign} moon sign {life_domain} predictions",
        ]

        for yoga in chart.active_yogas[:3]:
            queries.append(f"{yoga.name} yoga effects {life_domain}")

        for transit in chart.active_transits[:2]:
            queries.append(f"{transit.planet} transit {transit.to_sign} {life_domain}")

        return queries[:6]

    def retrieve(
        self,
        user_query: str,
        chart: ChartState,
        life_domain: str = "general",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        sub_queries = self.formulate_queries(user_query, chart, life_domain)
        logger.debug(f"RAG sub-queries: {sub_queries}")

        if self.enable_remote and self.embedder is not None:
            try:
                remote_results = self._retrieve_remote(sub_queries, top_k)
                if remote_results:
                    return remote_results
            except Exception as exc:
                logger.warning(f"Remote retrieval failed, falling back to local corpus: {exc}")

        return self._retrieve_local(sub_queries, top_k)

    def _retrieve_remote(self, sub_queries: List[str], top_k: int) -> List[Dict[str, Any]]:
        all_results: Dict[int, Dict[str, Any]] = {}

        for query in sub_queries:
            query_vector = self.embedder.embed_query(query)
            for collection in SEARCH_COLLECTIONS:
                results = hybrid_search(
                    collection_name=collection,
                    query_text=query,
                    query_vector=query_vector,
                    limit=10,
                    alpha=0.75,
                )
                for rank, result in enumerate(results):
                    key = hash(result["text"][:100])
                    if key not in all_results:
                        all_results[key] = {**result, "_rrf_score": 0.0, "_appearances": 0}
                    all_results[key]["_rrf_score"] += 1.0 / (60 + rank + 1)
                    all_results[key]["_appearances"] += 1

        ranked = sorted(all_results.values(), key=lambda item: item["_rrf_score"], reverse=True)
        top_results = ranked[:top_k]
        logger.info(f"Remote RAG retrieval: {len(all_results)} candidates -> top {len(top_results)}")
        return top_results

    def _retrieve_local(self, sub_queries: List[str], top_k: int) -> List[Dict[str, Any]]:
        documents = _load_local_documents()
        if not documents:
            return []

        doc_freq: Counter[str] = Counter()
        tokenized_docs: List[List[str]] = []
        for document in documents:
            tokens = _tokenize(document["text"])
            tokenized_docs.append(tokens)
            for token in set(tokens):
                doc_freq[token] += 1

        total_docs = len(documents)
        scored: Dict[int, Dict[str, Any]] = {}
        for query in sub_queries:
            query_tokens = _tokenize(query)
            if not query_tokens:
                continue
            query_counts = Counter(query_tokens)
            for index, document in enumerate(documents):
                doc_tokens = tokenized_docs[index]
                if not doc_tokens:
                    continue
                doc_counts = Counter(doc_tokens)
                score = 0.0
                for token, query_count in query_counts.items():
                    if token not in doc_counts:
                        continue
                    idf = math.log((1 + total_docs) / (1 + doc_freq[token])) + 1
                    score += query_count * doc_counts[token] * idf
                if score <= 0:
                    continue
                existing = scored.setdefault(
                    index,
                    {
                        "text": document["text"],
                        "source_ref": document["source_ref"],
                        "collection": document["collection"],
                        "_score": 0.0,
                    },
                )
                existing["_score"] += score

        ranked = sorted(scored.values(), key=lambda item: item["_score"], reverse=True)[:top_k]
        logger.info(f"Local retrieval: {len(scored)} scored passages -> top {len(ranked)}")
        return [
            {
                "text": item["text"],
                "source_ref": item["source_ref"],
                "collection": item["collection"],
                "score": round(item["_score"], 3),
            }
            for item in ranked
        ]

    def format_context(self, retrieved: List[Dict[str, Any]]) -> str:
        if not retrieved:
            return "No specific astrological references retrieved."

        lines = ["ASTROLOGICAL KNOWLEDGE BASE REFERENCES:\n"]
        for index, document in enumerate(retrieved, start=1):
            source = document.get("source_ref", "classical_source")
            text = document.get("text", "").strip()
            if text:
                lines.append(f"[REF {index}] ({source})\n{text}\n")

        return "\n".join(lines)


_retriever: RAGRetriever | None = None


def get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
