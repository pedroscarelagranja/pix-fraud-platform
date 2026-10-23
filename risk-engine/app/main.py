from fastapi import FastAPI

from .rules import avaliar
from .schemas import Decisao, Transacao

app = FastAPI(title="PIX Risk Engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/risk/evaluate", response_model=Decisao)
def evaluate(tx: Transacao) -> Decisao:
    return avaliar(tx)
