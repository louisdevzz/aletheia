"""
Documents API Routes

Document upload, ingestion, and management
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from aletheia.rag.pipeline.ingestion_pipeline import IngestionPipeline
from aletheia.rag.storage import get_storage
from aletheia.rag.storage.sqlite_store import SQLiteStore
from aletheia.daemon.websocket.manager import manager as ws_manager

router = APIRouter(tags=["documents"])

# Upload directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class DocumentResponse(BaseModel):
    doc_id: str
    filename: str
    total_pages: int
    created_at: str
    status: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    """
    Upload and ingest a PDF document.

    The document is saved and ingestion happens in the background.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save uploaded file first to get the path
    temp_doc_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{temp_doc_id}_{file.filename}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    finally:
        file.file.close()

    # Insert document into database with processing status
    storage = SQLiteStore()
    doc_id = storage.insert_document(
        filename=file.filename,
        total_pages=0,  # Will be updated during ingestion
        metadata={"source_path": str(file_path)},
        status="processing",
    )

    # Rename file with actual doc_id
    new_file_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    os.rename(file_path, new_file_path)

    # Start ingestion in background
    background_tasks.add_task(
        ingest_document_task, str(new_file_path), doc_id, file.filename
    )

    return DocumentResponse(
        doc_id=doc_id,
        filename=file.filename,
        total_pages=0,  # Will be updated after ingestion
        created_at=datetime.now().isoformat(),
        status="processing",
    )


def _broadcast_sync(message: dict):
    """Safely broadcast WebSocket message from sync context."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        # If there's already a loop running, use run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), loop)
        future.result(timeout=5)  # Wait up to 5 seconds
    except RuntimeError:
        # No loop running, create a new one
        asyncio.run(ws_manager.broadcast(message))


def ingest_document_task(file_path: str, doc_id: str, filename: str):
    """Background task for document ingestion."""
    storage = SQLiteStore()
    try:
        pipeline = IngestionPipeline()
        # Pass doc_id to pipeline so it updates existing record instead of creating new
        result_doc_id = pipeline.ingest_document(file_path, filename, doc_id=doc_id)
        # Update status to completed
        storage.update_document_status(doc_id, "completed")
        print(f"✓ Ingested document: {filename} (ID: {result_doc_id})")

        # Broadcast completion to all WebSocket clients
        _broadcast_sync(
            {
                "type": "document.ingested",
                "doc_id": doc_id,
                "filename": filename,
                "status": "completed",
            }
        )
    except Exception as e:
        # Update status to failed
        storage.update_document_status(doc_id, "failed")
        print(f"✗ Failed to ingest {filename}: {e}")

        # Broadcast failure to all WebSocket clients
        _broadcast_sync(
            {
                "type": "document.ingested",
                "doc_id": doc_id,
                "filename": filename,
                "status": "failed",
                "error": str(e),
            }
        )

        import traceback

        traceback.print_exc()
    finally:
        # Clean up uploaded file
        try:
            os.remove(file_path)
        except:
            pass


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """
    List all uploaded documents.
    """
    try:
        storage = get_storage()
        docs = storage.get_all_documents()

        documents = [
            DocumentResponse(
                doc_id=doc["doc_id"],
                filename=doc["filename"],
                total_pages=doc["total_pages"],
                created_at=doc["created_at"],
                status=doc.get("status", "completed"),
            )
            for doc in docs
        ]

        return DocumentListResponse(documents=documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str):
    """
    Get document details by ID.
    """
    try:
        storage = get_storage()
        doc = storage.get_document(doc_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentResponse(
            doc_id=doc["doc_id"],
            filename=doc["filename"],
            total_pages=doc["total_pages"],
            created_at=doc["created_at"],
            status=doc.get("status", "completed"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document and all its data.
    """
    try:
        storage = get_storage()
        storage.delete_document(doc_id)
        return {"message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
