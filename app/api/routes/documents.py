from fastapi import APIRouter, HTTPException

from app.schemas.documents import ListPdfRequest, ListPdfResponse
from app.service.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])
service = DocumentService()


@router.post("/list", response_model=ListPdfResponse)
async def list_pdfs(body: ListPdfRequest) -> ListPdfResponse:
    try:
        return await service.list_pdfs(body.folder)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
