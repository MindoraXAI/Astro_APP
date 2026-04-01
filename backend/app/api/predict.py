"""
AIS Prediction API Routes
POST /api/predict — full ALM pipeline → structured PredictionOutput
POST /api/predict/seed — seed Weaviate knowledge base with NVIDIA NIM embeddings
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger

from app.core.models import QueryRequest, PredictionOutput

router = APIRouter()


@router.post("", response_model=PredictionOutput, summary="Full ALM Prediction")
async def predict(request: QueryRequest):
    """
    Run the complete ALM pipeline:
    Chart Computation → Yoga Detection → RAG Retrieval → Ollama LLM → Guardrails → Citation

    Returns structured PredictionOutput with:
    - Full ChartState
    - Predictions with confidence scores and evidence chains
    - Personality archetypes
    - Classical source references
    """
    try:
        from app.alm.orchestrator import run_alm

        result = await run_alm(request)
        return result
    except Exception as e:
        logger.error(f"ALM prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/seed", summary="Seed Weaviate Knowledge Base")
async def seed_knowledge_base(background_tasks: BackgroundTasks):
    """
    Seed the Weaviate vector store with the Phase 1 astrological knowledge base.
    Uses NVIDIA NIM nemotron-embed-1b-v2 for embedding.

    This runs as a background task and may take 2-5 minutes.
    """
    background_tasks.add_task(_run_seeder)
    return {
        "status": "seeding_started",
        "message": "Knowledge base seeding started in background. Check logs for progress.",
        "collections": [
            "YogaDescription",
            "DashaEffect",
            "TransitEffect",
            "PlanetSignification",
            "HouseLordEffect",
            "HistoricalChartExample",
        ],
    }


async def _run_seeder():
    """Background task: embed and insert all seed data into Weaviate."""
    from app.rag.seed_data.knowledge_base import ALL_SEED_DATA
    from app.rag.embedder import get_embedder
    from app.rag.weaviate_client import insert_objects, init_weaviate_schema

    try:
        logger.info("Starting knowledge base seeding...")
        await init_weaviate_schema()
        embedder = get_embedder()

        total_inserted = 0
        for collection_name, items in ALL_SEED_DATA.items():
            if not items:
                continue
            texts = [item.get("full_text", "") for item in items]
            vectors = embedder.embed_passages(texts)
            insert_objects(collection_name, items, vectors)
            total_inserted += len(items)
            logger.info(f"Seeded {len(items)} items into {collection_name}")

        logger.info(f"✅ Knowledge base seeding complete: {total_inserted} total items")
    except Exception as e:
        logger.error(f"Seeder failed: {e}")
