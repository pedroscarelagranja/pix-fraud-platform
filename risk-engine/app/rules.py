from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .schemas import Decisao, Transacao

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")

# Limiares iniciais (didaticos). Depois viram perfil por usuario no Redis.
VALOR_ALTO = 5000.0
JANELA_CHAVE_RECENTE = timedelta(hours=24)
HORA_INICIO_MADRUGADA = 0
HORA_FIM_MADRUGADA = 5  # exclusivo

LIMIAR_BLOQUEIO = 70
LIMIAR_REVISAO = 40


def _utc(dt: datetime) -> datetime:
    """Assume UTC quando a data vem sem fuso, para evitar erro naive vs aware."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def avaliar(tx: Transacao) -> Decisao:
    score = 0
    motivos: list[str] = []

    if tx.valor >= VALOR_ALTO:
        score += 40
        motivos.append("valor_alto")

    hora_local = _utc(tx.timestamp).astimezone(FUSO_BRASIL).hour
    if HORA_INICIO_MADRUGADA <= hora_local < HORA_FIM_MADRUGADA:
        score += 20
        motivos.append("horario_atipico")

    if tx.chave_criada_em is not None:
        idade_chave = _utc(tx.timestamp) - _utc(tx.chave_criada_em)
        if idade_chave < JANELA_CHAVE_RECENTE:
            score += 40
            motivos.append("chave_recente")

    if score >= LIMIAR_BLOQUEIO:
        decisao = "BLOQUEADA"
    elif score >= LIMIAR_REVISAO:
        decisao = "EM_REVISAO"
    else:
        decisao = "APROVADA"

    return Decisao(transacao_id=tx.id, decisao=decisao, score=score, motivos=motivos)
