from pydantic import BaseModel


class ListPdfRequest(BaseModel):
    folder: str

    model_config = {
        "json_schema_extra": {
            "example": {"folder": "D:\\TrabajosPosgrado\\ProyectoGrado\\DesarrolloSoftware\\HerramientaAnonimizadora\\tests\\aprocesar"}
        }
    }


class PdfFileInfo(BaseModel):
    name: str
    size_bytes: int
    path: str


class ListPdfResponse(BaseModel):
    total: int
    files: list[PdfFileInfo]
