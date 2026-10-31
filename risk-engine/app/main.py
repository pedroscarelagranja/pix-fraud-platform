import logging
import os
from functools import lru_cache

import redis
from fastapi import Depends, FastAPI

from .profile import PerfilStore
from .rules import avaliar
from .schemas import Decisao, Transacao

log = logging.getLogger("risk-engine")

app = FastAPI(title="PIX Risk Engine", version="0.2.0")


@lru_cache
def get_store() -> PerfilStore:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.3)
    return PerfilStore(client)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/risk/evaluate", response_model=Decisao)
def evaluate(tx: Transacao, store: PerfilStore = Depends(get_store)) -> Decisao:
    perfil = None
    tentativas = 0
    try:
        tentativas = store.registrar_tentativa(tx.conta_origem)
        perfil = store.obter(tx.conta_origem)
    except redis.RedisError:
        # Modo degradado: sem Redis, avalia so com as regras que nao dependem de historico.
        log.warning("Redis indisponivel; avaliando sem perfil do usuario")

    resultado = avaliar(tx, perfil, tentativas)

    # So aprendemos o "habito" com transacoes nao bloqueadas, para um golpe nao
    # contaminar a media do usuario.
    if resultado.decisao != "BLOQUEADA" and perfil is not None:
        try:
            store.atualizar(tx.conta_origem, tx.valor)
        except redis.RedisError:
            log.warning("Redis indisponivel; perfil nao atualizado")

    return resultado
