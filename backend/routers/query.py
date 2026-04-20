"""
Query Router
============
POST /query  — Full RAG pipeline with intent + emotion detection
"""

import time
import uuid
from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    EmotionResult, IntentResult, Intent, Emotion,
    QueryRequest, QueryResponse, RetrievedChunk,
)
from backend.services.detection import IntentEmotionDetector
from backend.services.generation import ResponseGenerator
from backend.services.ingestion import DocumentIngestionService
from backend.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)

# Singletons
_ingestion = DocumentIngestionService()
_detector = IntentEmotionDetector()
_generator = ResponseGenerator()


@router.post("", response_model=QueryResponse)
async def query_documents(req: QueryRequest):
    """
    Full RAG query pipeline.

    Flow:
    1. Detect intent and emotion (rule-based → LLM fallback)
    2. Retrieve top-K relevant chunks from vector store
    3. Determine response tone from intent × emotion matrix
    4. Generate LLM answer conditioned on context + tone

    **Sample request:**
    ```json
    {
      "query": "What is your return policy?",
      "user_id": "user_123",
      "document_ids": null,
      "top_k": 5
    }
    ```
    """
    t0 = time.perf_counter()

    try:
        # 1. Intent + Emotion
        intent_result, emotion_result = await _detector.detect(req.query)

        # 2. Retrieval
        chunks = await _ingestion.search(
            user_id=req.user_id,
            query=req.query,
            top_k=req.top_k or 5,
            document_ids=req.document_ids,
        )

        # 3. Tone
        intent_enum = Intent(intent_result.label)
        emotion_enum = Emotion(emotion_result.label)
        tone = _detector.get_response_tone(intent_enum, emotion_enum)

        # 4. Generation
        answer, fallback = await _generator.generate_rag_answer(
            query=req.query,
            chunks=chunks,
            intent=intent_enum,
            emotion=emotion_enum,
            tone=tone,
        )

        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            f"Query processed | intent={intent_result.label} "
            f"emotion={emotion_result.label} tone={tone} "
            f"chunks={len(chunks)} latency={latency_ms:.1f}ms"
        )

        return QueryResponse(
            query=req.query,
            intent=IntentResult(
                intent=intent_enum,
                confidence=intent_result.confidence,
                is_low_confidence=intent_result.is_low_confidence,
            ),
            emotion=EmotionResult(
                emotion=emotion_enum,
                confidence=emotion_result.confidence,
                is_low_confidence=emotion_result.is_low_confidence,
            ),
            response_tone=tone,
            answer=answer,
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    filename=c.filename,
                    content=c.content,
                    score=c.score,
                    page=c.page,
                )
                for c in chunks
            ],
            fallback_triggered=fallback,
            latency_ms=round(latency_ms, 2),
        )

    except Exception as e:
        logger.error(f"Query pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Query processing failed.")