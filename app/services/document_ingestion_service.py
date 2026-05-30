"""Tenant-owned document ingestion for RAG chunks."""
from __future__ import annotations

import logging
import re
import uuid
from io import BytesIO
from typing import Iterable

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _chunk_text(page_texts: Iterable[tuple[int, str]], max_chars: int = 1400, overlap: int = 180) -> list[dict]:
    chunks: list[dict] = []
    chunk_index = 0

    for page_number, raw_text in page_texts:
        text = _normalize_text(raw_text)
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "chunk_text": chunk,
                })
                chunk_index += 1
            if end >= len(text):
                break
            start = max(0, end - overlap)

    return chunks


def _extract_pdf_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PyMuPDF is required for backend PDF ingestion",
        ) from exc

    pages: list[tuple[int, str]] = []
    with fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf") as doc:
        for index, page in enumerate(doc, start=1):
            pages.append((index, page.get_text("text")))
    return pages


class DocumentIngestionService:
    @staticmethod
    async def _embed_texts(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/v1/embeddings/text"
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, json={"texts": texts})
            response.raise_for_status()
            data = response.json()

        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI embedding service returned invalid embedding count",
            )
        return embeddings

    @staticmethod
    async def ingest_pdf_bytes(db: Session, document_id: str, pdf_bytes: bytes) -> int:
        document_uuid = uuid.UUID(str(document_id))
        document = db.query(Document).filter(Document.id == document_uuid).first()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        pages = _extract_pdf_pages(pdf_bytes)
        chunks = _chunk_text(pages)
        if not chunks:
            logger.warning("No text chunks extracted for document %s", document_id)
            return 0

        embeddings: list[list[float]] = []
        batch_size = 64
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            embeddings.extend(await DocumentIngestionService._embed_texts([item["chunk_text"] for item in batch]))

        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(synchronize_session=False)
        for chunk, embedding in zip(chunks, embeddings):
            db.add(DocumentChunk(
                document_id=document.id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk["page_number"],
                chunk_text=chunk["chunk_text"],
                embedding=embedding,
            ))

        db.commit()
        logger.info("Indexed %s chunks for document %s", len(chunks), document_id)
        return len(chunks)
