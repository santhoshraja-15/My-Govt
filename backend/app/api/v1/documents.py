"""Documents & policies API endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.documents import DocumentListResponse, DocumentDetail
from app.schemas.services import PolicyDocumentList, PolicyDocumentOut
from app.services.document_service import DocumentService
from app.services.other_services import PolicyDocumentService

router = APIRouter()


@router.get("/policy", response_model=PolicyDocumentList)
async def list_policy_documents(
    q: Optional[str] = Query(None, max_length=200),
    category: Optional[str] = Query(None, pattern="^(government_order|policy|circular|notification|act)(,(government_order|policy|circular|notification|act))*$", description="One category or a comma-separated list"),
    authority: Optional[str] = Query(None, max_length=200),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    language: Optional[str] = Query(None, pattern="^(en|ta|bilingual)$"),
    verification_status: Optional[str] = Query(None, max_length=40),
    sort: str = Query("newest", pattern="^(newest|oldest|title)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Official policy-document catalogue (Government Orders and policies, circulars, notifications, Acts)."""
    return await PolicyDocumentService(db).list(q, category, authority, year, language, verification_status, sort, page, page_size)


@router.get("/policy/{doc_code}", response_model=PolicyDocumentOut)
async def get_policy_document(doc_code: str, db: AsyncSession = Depends(get_db)):
    doc = await PolicyDocumentService(db).get(doc_code)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    q: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None, description="government_order|policy|law|notice|announcement"),
    department_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = DocumentService(db)
    return await svc.list_documents(q=q, doc_type=doc_type,
                                     department_id=department_id,
                                     page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = DocumentService(db)
    doc = await svc.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/search/full-text")
async def full_text_search(
    q: str = Query(..., min_length=2),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    svc = DocumentService(db)
    return await svc.hybrid_search(q=q, doc_type=doc_type, limit=limit)
