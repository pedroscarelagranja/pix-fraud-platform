from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Transacao(BaseModel):
    id: str
    conta_origem: str
    chave_destino: str
    valor: float = Field(gt=0)
    timestamp: datetime
    # Quando a chave PIX de destino foi criada (se conhecido)
    chave_criada_em: datetime | None = None


class Decisao(BaseModel):
    transacao_id: str
    decisao: Literal["APROVADA", "EM_REVISAO", "BLOQUEADA"]
    score: int
    motivos: list[str]
