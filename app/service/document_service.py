import asyncio

from app.logic import document_logic
from app.schemas.documents import ListPdfResponse, PdfFileInfo


class DocumentService:
    """Casos de uso de documentos. Orquesta la lógica y arma la respuesta."""

    async def list_pdfs(self, folder: str) -> ListPdfResponse:
        path = document_logic.validate_folder(folder)
        # Lectura de disco en un hilo para no bloquear el event loop
        pdfs = await asyncio.to_thread(document_logic.find_pdfs, path)
        files = [
            PdfFileInfo(name=p.name, size_bytes=p.stat().st_size, path=str(p))
            for p in pdfs
        ]
        return ListPdfResponse(total=len(files), files=files)
