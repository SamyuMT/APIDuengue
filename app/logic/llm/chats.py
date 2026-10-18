import re
import uuid
from datetime import datetime

from app.core.rutas import DATA_DIR
from app.schemas.llm import Chat, Mensaje

CHATS_DIR = DATA_DIR / "llm" / "chats"
_ID_VALIDO = re.compile(r"^[\w-]+$")


def crear(modelo: str, system: str | None) -> Chat:
    chat = Chat(chat_id=f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}", modelo=modelo)
    if system:
        chat.mensajes.append(Mensaje(rol="system", contenido=system))
    guardar(chat)
    return chat


def cargar(chat_id: str) -> Chat | None:
    ruta = CHATS_DIR / f"{chat_id}.json"
    if not _ID_VALIDO.match(chat_id) or not ruta.exists():
        return None
    return Chat.model_validate_json(ruta.read_text(encoding="utf-8"))


def guardar(chat: Chat) -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    destino = CHATS_DIR / f"{chat.chat_id}.json"
    temporal = destino.with_suffix(".tmp")
    temporal.write_text(chat.model_dump_json(indent=2), encoding="utf-8")
    temporal.replace(destino)
