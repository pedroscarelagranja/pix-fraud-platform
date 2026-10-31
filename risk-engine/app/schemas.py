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


class PerfilUsuario(BaseModel):
    """Resumo do habito de uma conta: quantas transacoes aprovadas e o valor medio."""

    qtd: int = 0
    media: float = 0.0


class Decisao(BaseModel):
    transacao_id: str
    decisao: Literal["APROVADA", "EM_REVISAO", "BLOQUEADA"]
    score: int
    motivos: list[str]
