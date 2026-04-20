"""
Document Ingestion Service
==========================
Handles: text extraction → chunking → embedding → vector storage

Supports: PDF, DOCX, TXT, MD, CSV
Vector Store: ChromaDB (default) — swap to Pinecone/Qdrant via settings
"""

import asyncio
import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI

from backend.config.settings import settings
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    user_id: str
    filename: str
    content: str
    page: Optional[int]
    chunk_index: int
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    filename: str
    content: str
    score: float
    page: Optional[int]


# ── Text Extractors ──────────────────────────────────────────────────────────

class TextExtractor:
    """Extracts raw text from various file types."""

    @staticmethod
    def from_bytes(file_bytes: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        extractors = {
            ".pdf": TextExtractor._from_pdf,
            ".docx": TextExtractor._from_docx,
            ".txt": TextExtractor._from_text,
            ".md": TextExtractor._from_text,
            ".csv": TextExtractor._from_text,
        }
        extractor = extractors.get(ext)
        if not extractor:
            raise ValueError(f"Unsupported file type: {ext}")
        return extractor(file_bytes)

    @staticmethod
    def _from_pdf(file_bytes: bytes) -> str:
        """Extract text from PDF using PyMuPDF (fitz)."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text("text")
                if text.strip():
                    pages.append(f"[Page {i+1}]\n{text}")
            return "\n\n".join(pages)
        except ImportError:
            # Fallback to pdfplumber
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n\n".join(
                    f"[Page {i+1}]\n{page.extract_text() or ''}"
                    for i, page in enumerate(pdf.pages)
                )

    @staticmethod
    def _from_docx(file_bytes: bytes) -> str:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    @staticmethod
    def _from_text(file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="replace")


# ── Chunker ──────────────────────────────────────────────────────────────────

class RecursiveChunker:
    """
    Recursive character-based chunker with overlap.
    Strategy:
      1. Split on paragraphs (double newline)
      2. If chunk too large → split on sentences
      3. If still too large → hard split on tokens
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, document_id: str, user_id: str, filename: str) -> List[Chunk]:
        raw_chunks = self._split(text)
        chunks = []
        for i, content in enumerate(raw_chunks):
            content = content.strip()
            if not content:
                continue
            # Try to detect page number hints like "[Page 3]"
            page = None
            import re
            m = re.search(r"\[Page (\d+)\]", content)
            if m:
                page = int(m.group(1))

            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                user_id=user_id,
                filename=filename,
                content=content,
                page=page,
                chunk_index=i,
            ))
        logger.info(f"Chunked document '{filename}' → {len(chunks)} chunks")
        return chunks

    def _split(self, text: str) -> List[str]:
        """Recursively split text into chunks of ~chunk_size chars."""
        separators = ["\n\n", "\n", ". ", " ", ""]
        return self._recursive_split(text, separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]
        sep = separators[0] if separators else ""
        splits = text.split(sep) if sep else list(text)
        chunks: List[str] = []
        current = ""
        for part in splits:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # if this single part is still too large, recurse
                if len(part) > self.chunk_size and len(separators) > 1:
                    chunks.extend(self._recursive_split(part, separators[1:]))
                    current = ""
                else:
                    current = part
        if current:
            chunks.append(current)

        # Add overlap: append start of next chunk to end of current
        if self.chunk_overlap > 0:
            overlapped: List[str] = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    overlap = chunks[i - 1][-self.chunk_overlap:]
                    chunk = overlap + " " + chunk
                overlapped.append(chunk)
            return overlapped
        return chunks


# ── Embedding Service ────────────────────────────────────────────────────────

class EmbeddingService:
    """Generates embeddings via OpenAI (or local model)."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL
        self._batch_size = 100  # OpenAI max

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts in batches."""
        if not texts:
            return []
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i: i + self._batch_size]
            response = await self.client.embeddings.create(
                input=batch,
                model=self.model,
            )
            all_embeddings.extend([item.embedding for item in response.data])
        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        result = await self.embed_texts([query])
        return result[0]


# ── Vector Store ─────────────────────────────────────────────────────────────

class VectorStore:
    """
    ChromaDB-backed vector store.
    Collection naming: one collection per user → easy data isolation.
    Swap to Pinecone: replace _get_collection / upsert / query methods.
    """

    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _collection_name(self, user_id: str) -> str:
        # Sanitize user_id for collection name
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return f"user_{safe}"

    def _get_collection(self, user_id: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(user_id),
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: List[Chunk]) -> None:
        """Store chunks + embeddings into ChromaDB."""
        if not chunks:
            return
        if not chunks[0].embedding:
            raise ValueError("Chunks must have embeddings before upsert")

        user_id = chunks[0].user_id
        col = self._get_collection(user_id)

        col.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=[c.embedding for c in chunks],
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    "document_id": c.document_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                    "page": c.page or 0,
                }
                for c in chunks
            ],
        )
        logger.info(f"Upserted {len(chunks)} chunks for user '{user_id}'")

    def search(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        col = self._get_collection(user_id)

        where: Optional[Dict] = None
        if document_ids:
            where = {"document_id": {"$in": document_ids}}

        results = col.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        search_results: List[SearchResult] = []
        for i, (doc, meta, dist) in enumerate(
            zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
        ):
            # ChromaDB cosine distance → similarity score
            score = 1.0 - dist
            search_results.append(SearchResult(
                chunk_id=results["ids"][0][i],
                document_id=meta["document_id"],
                filename=meta["filename"],
                content=doc,
                score=score,
                page=meta.get("page") or None,
            ))
        return search_results

    def delete_document(self, user_id: str, document_id: str) -> None:
        col = self._get_collection(user_id)
        # Get all IDs for this document, then delete
        existing = col.get(where={"document_id": document_id})
        if existing["ids"]:
            col.delete(ids=existing["ids"])
            logger.info(f"Deleted {len(existing['ids'])} chunks for doc '{document_id}'")

    def list_documents(self, user_id: str) -> List[Dict[str, Any]]:
        col = self._get_collection(user_id)
        results = col.get(include=["metadatas"])
        seen: Dict[str, Dict] = {}
        for meta in results["metadatas"]:
            doc_id = meta["document_id"]
            if doc_id not in seen:
                seen[doc_id] = {
                    "document_id": doc_id,
                    "filename": meta["filename"],
                    "num_chunks": 0,
                }
            seen[doc_id]["num_chunks"] += 1
        return list(seen.values())


# ── Ingestion Service (orchestrator) ────────────────────────────────────────

class DocumentIngestionService:
    """
    End-to-end ingestion pipeline:
    file_bytes → extract → chunk → embed → store
    """

    def __init__(self):
        self.extractor = TextExtractor()
        self.chunker = RecursiveChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self.embedder = EmbeddingService()
        self.vector_store = VectorStore()

    async def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        document_id = document_id or str(uuid.uuid4())

        # 1. Extract text
        logger.info(f"[Ingest] Extracting text from '{filename}'")
        text = self.extractor.from_bytes(file_bytes, filename)
        if not text.strip():
            raise ValueError("Document appears to be empty or unreadable.")

        # 2. Chunk
        logger.info(f"[Ingest] Chunking text ({len(text)} chars)")
        chunks = self.chunker.chunk(text, document_id, user_id, filename)

        # 3. Embed
        logger.info(f"[Ingest] Embedding {len(chunks)} chunks")
        texts = [c.content for c in chunks]
        embeddings = await self.embedder.embed_texts(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        # 4. Store
        self.vector_store.upsert_chunks(chunks)

        return {
            "document_id": document_id,
            "filename": filename,
            "num_chunks": len(chunks),
            "text_length": len(text),
        }

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        query_embedding = await self.embedder.embed_query(query)
        return self.vector_store.search(user_id, query_embedding, top_k, document_ids)