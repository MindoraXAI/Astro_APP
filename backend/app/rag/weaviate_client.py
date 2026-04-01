"""
AIS Weaviate Client
Manages Weaviate schema, collections, and CRUD for the RAG knowledge base.

Collections:
- YogaDescription: classical yoga rules + interpretations
- PlanetSignification: planetary meanings, significations, karakas
- HouseLordEffect: planet-in-sign and house lord effects
- DashaEffect: mahadasha + antardasha interpretations
- TransitEffect: gochara (transit) effects per planet-house combo
- HistoricalChartExample: famous charts with known life outcomes
"""
from __future__ import annotations

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Configure, Property, DataType, VectorDistances
from loguru import logger
from typing import Dict, List, Optional, Any
import asyncio

from app.core.config import settings


# ─── Collection Definitions ───────────────────────────────────────────────────

COLLECTIONS = {
    "YogaDescription": {
        "description": "Classical yoga formation rules and their interpretive effects",
        "properties": [
            Property(name="yoga_name", data_type=DataType.TEXT),
            Property(name="category", data_type=DataType.TEXT),
            Property(name="tradition", data_type=DataType.TEXT),
            Property(name="formation_rule", data_type=DataType.TEXT),
            Property(name="effect_career", data_type=DataType.TEXT),
            Property(name="effect_personality", data_type=DataType.TEXT),
            Property(name="effect_health", data_type=DataType.TEXT),
            Property(name="effect_relationships", data_type=DataType.TEXT),
            Property(name="effect_finance", data_type=DataType.TEXT),
            Property(name="source_ref", data_type=DataType.TEXT),
            Property(name="strength_modifier", data_type=DataType.NUMBER),
            Property(name="full_text", data_type=DataType.TEXT),  # searchable chunk
        ],
    },
    "PlanetSignification": {
        "description": "Planetary natural significations, karakatvas, and domain associations",
        "properties": [
            Property(name="planet", data_type=DataType.TEXT),
            Property(name="sign", data_type=DataType.TEXT),
            Property(name="dignity", data_type=DataType.TEXT),
            Property(name="significations", data_type=DataType.TEXT_ARRAY),
            Property(name="career_domains", data_type=DataType.TEXT_ARRAY),
            Property(name="health_domains", data_type=DataType.TEXT_ARRAY),
            Property(name="relationship_quality", data_type=DataType.TEXT),
            Property(name="tradition", data_type=DataType.TEXT),
            Property(name="full_text", data_type=DataType.TEXT),
        ],
    },
    "HouseLordEffect": {
        "description": "Effects of house lords placed in different houses",
        "properties": [
            Property(name="lord_of_house", data_type=DataType.INT),
            Property(name="placed_in_house", data_type=DataType.INT),
            Property(name="effect_summary", data_type=DataType.TEXT),
            Property(name="career_effect", data_type=DataType.TEXT),
            Property(name="health_effect", data_type=DataType.TEXT),
            Property(name="relationship_effect", data_type=DataType.TEXT),
            Property(name="tradition", data_type=DataType.TEXT),
            Property(name="source_ref", data_type=DataType.TEXT),
            Property(name="full_text", data_type=DataType.TEXT),
        ],
    },
    "DashaEffect": {
        "description": "Vimshottari mahadasha and antardasha interpretations",
        "properties": [
            Property(name="mahadasha", data_type=DataType.TEXT),
            Property(name="antardasha", data_type=DataType.TEXT),
            Property(name="general_effect", data_type=DataType.TEXT),
            Property(name="career_effect", data_type=DataType.TEXT),
            Property(name="health_effect", data_type=DataType.TEXT),
            Property(name="relationship_effect", data_type=DataType.TEXT),
            Property(name="finance_effect", data_type=DataType.TEXT),
            Property(name="duration_years", data_type=DataType.NUMBER),
            Property(name="source_ref", data_type=DataType.TEXT),
            Property(name="full_text", data_type=DataType.TEXT),
        ],
    },
    "TransitEffect": {
        "description": "Gochara (transit) effects of planets through houses from natal Moon",
        "properties": [
            Property(name="planet", data_type=DataType.TEXT),
            Property(name="house_from_moon", data_type=DataType.INT),
            Property(name="general_effect", data_type=DataType.TEXT),
            Property(name="career_effect", data_type=DataType.TEXT),
            Property(name="health_effect", data_type=DataType.TEXT),
            Property(name="relationship_effect", data_type=DataType.TEXT),
            Property(name="auspicious", data_type=DataType.BOOL),
            Property(name="source_ref", data_type=DataType.TEXT),
            Property(name="full_text", data_type=DataType.TEXT),
        ],
    },
    "HistoricalChartExample": {
        "description": "Famous charts with known life outcomes for comparative analysis",
        "properties": [
            Property(name="person_name", data_type=DataType.TEXT),
            Property(name="field", data_type=DataType.TEXT),
            Property(name="lagna", data_type=DataType.TEXT),
            Property(name="moon_sign", data_type=DataType.TEXT),
            Property(name="notable_yogas", data_type=DataType.TEXT_ARRAY),
            Property(name="career_outcome", data_type=DataType.TEXT),
            Property(name="life_summary", data_type=DataType.TEXT),
            Property(name="tradition", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
            Property(name="full_text", data_type=DataType.TEXT),
        ],
    },
}


# ─── Client ───────────────────────────────────────────────────────────────────

class WeaviateClient:
    """Manages Weaviate connection, schema, and CRUD operations."""

    def __init__(self):
        self._client: Optional[weaviate.WeaviateClient] = None

    def connect(self):
        """Establish Weaviate connection."""
        self._client = weaviate.connect_to_local(
            host=settings.WEAVIATE_URL.replace("http://", "").split(":")[0],
            port=int(settings.WEAVIATE_URL.split(":")[-1]),
            grpc_port=settings.WEAVIATE_GRPC_PORT,
        )
        logger.info(f"Weaviate connected: {settings.WEAVIATE_URL}")
        return self

    def get_client(self) -> weaviate.WeaviateClient:
        if self._client is None:
            self.connect()
        return self._client

    def is_ready(self) -> bool:
        try:
            return self.get_client().is_ready()
        except Exception:
            return False


async def init_weaviate_schema():
    """Initialize all Weaviate collections if they don't exist."""
    try:
        client = weaviate.connect_to_local(
            host=settings.WEAVIATE_URL.replace("http://", "").split(":")[0],
            port=int(settings.WEAVIATE_URL.split(":")[-1]),
            grpc_port=settings.WEAVIATE_GRPC_PORT,
        )

        for collection_name, config in COLLECTIONS.items():
            if not client.collections.exists(collection_name):
                client.collections.create(
                    name=collection_name,
                    description=config["description"],
                    properties=config["properties"],
                    # No vectorizer — we supply vectors from NVIDIA NIM
                    vectorizer_config=Configure.Vectorizer.none(),
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=VectorDistances.COSINE
                    ),
                )
                logger.info(f"Created Weaviate collection: {collection_name}")
            else:
                logger.debug(f"Weaviate collection exists: {collection_name}")

        client.close()
    except Exception as e:
        logger.error(f"Weaviate schema init failed: {e}")
        raise


def insert_objects(
    collection_name: str,
    objects: List[Dict[str, Any]],
    vectors: List[List[float]],
):
    """Batch insert objects with pre-computed NVIDIA NIM vectors."""
    client = weaviate.connect_to_local(
        host=settings.WEAVIATE_URL.replace("http://", "").split(":")[0],
        port=int(settings.WEAVIATE_URL.split(":")[-1]),
        grpc_port=settings.WEAVIATE_GRPC_PORT,
    )
    try:
        collection = client.collections.get(collection_name)
        with collection.batch.dynamic() as batch:
            for obj, vector in zip(objects, vectors):
                batch.add_object(properties=obj, vector=vector)
        logger.info(f"Inserted {len(objects)} objects into {collection_name}")
    finally:
        client.close()


def hybrid_search(
    collection_name: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 20,
    alpha: float = 0.75,  # 0=pure BM25, 1=pure vector
) -> List[Dict[str, Any]]:
    """
    Hybrid search combining dense (NVIDIA NIM vectors) + BM25 keyword retrieval.
    alpha=0.75 weights vector retrieval 75% and BM25 25%.
    """
    client = weaviate.connect_to_local(
        host=settings.WEAVIATE_URL.replace("http://", "").split(":")[0],
        port=int(settings.WEAVIATE_URL.split(":")[-1]),
        grpc_port=settings.WEAVIATE_GRPC_PORT,
    )
    try:
        collection = client.collections.get(collection_name)
        response = collection.query.hybrid(
            query=query_text,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            return_metadata=wvc.query.MetadataQuery(score=True, explain_score=True),
            return_properties=["full_text", "source_ref"],
        )
        results = []
        for obj in response.objects:
            results.append({
                "text": obj.properties.get("full_text", ""),
                "source_ref": obj.properties.get("source_ref", ""),
                "score": obj.metadata.score if obj.metadata else 0.0,
                "collection": collection_name,
            })
        return results
    finally:
        client.close()
