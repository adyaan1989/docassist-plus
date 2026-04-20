"""
Documents Router
================
POST /documents/upload  — Ingest a document
GET  /documents/{user_id} — List user documents
DELETE /documents/{user_id}/{document_id} — Remove document
"""

import time
import uuid
from datetime import datetime
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pathlib import Path

from backend.config.settings import settings
from backend.models.schemas import DocumentListResponse, DocumentUploadResponse
from backend.services.ingestion import DocumentIngestionService
from backend.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)

# Singleton ingestion service (shared across requests)
_ingestion_service = DocumentIngestionService()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    document_id: str = Form(None),
):
    """
    Upload and ingest a document.

    - Extracts text (PDF / DOCX / TXT / MD / CSV)
    - Chunks with overlap
    - Generates embeddings
    - Stores in vector database

    **Request (multipart/form-data):**
    ```
    file: <binary>
    user_id: "user_123"
    document_id: "doc_abc"   # optional; auto-generated if omitted
    ```
    """
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB",
        )

    try:
        result = await _ingestion_service.ingest(
            file_bytes=file_bytes,
            filename=file.filename,
            user_id=user_id,
            document_id=document_id,
        )
        return DocumentUploadResponse(
            document_id=result["document_id"],
            user_id=user_id,
            filename=result["filename"],
            num_chunks=result["num_chunks"],
            status="success",
            message=f"Document ingested successfully into {result['num_chunks']} chunks.",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to ingest document.")


@router.get("/{user_id}", response_model=DocumentListResponse)
async def list_documents(user_id: str):
    """List all documents for a user."""
    docs = _ingestion_service.vector_store.list_documents(user_id)
    return DocumentListResponse(
        user_id=user_id,
        documents=docs,
        total=len(docs),
    )


@router.delete("/{user_id}/{document_id}")
async def delete_document(user_id: str, document_id: str):
    """Delete a document and all its chunks from the vector store."""
    _ingestion_service.vector_store.delete_document(user_id, document_id)
    return {"status": "deleted", "document_id": document_id}