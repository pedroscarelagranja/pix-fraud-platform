from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.rules import avaliar
from app.schemas import Transacao

client = TestClient(app)
MEIO_DIA = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _tx(**kw) -> Transacao:
    base = dict(id="t1", conta_origem="c1", chave_destino="k1", valor=100.0, timestamp=MEIO_DIA)
    base.update(kw)
    return Transacao(**base)


def test_transacao_normal_e_aprovada():
    d = avaliar(_tx())
    assert d.decisao == "APROVADA" and d.score == 0


def test_valor_alto_vai_para_revisao():
    d = avaliar(_tx(valor=8000))
    assert d.decisao == "EM_REVISAO" and "valor_alto" in d.motivos


def test_valor_alto_para_chave_recente_e_bloqueada():
    d = avaliar(_tx(valor=8000, chave_criada_em=MEIO_DIA - timedelta(hours=2)))
    assert d.decisao == "BLOQUEADA"
    assert set(d.motivos) == {"valor_alto", "chave_recente"}


def test_madrugada_sozinha_nao_bloqueia():
    d = avaliar(_tx(timestamp=MEIO_DIA.replace(hour=3)))
    assert d.decisao == "APROVADA" and "horario_atipico" in d.motivos


def test_horario_usa_fuso_de_brasilia():
    # 02:30 UTC = 23:30 em Brasilia -> horario normal
    d1 = avaliar(_tx(timestamp=MEIO_DIA.replace(hour=2, minute=30)))
    assert "horario_atipico" not in d1.motivos
    # 06:00 UTC = 03:00 em Brasilia -> madrugada
    d2 = avaliar(_tx(timestamp=MEIO_DIA.replace(hour=6)))
    assert "horario_atipico" in d2.motivos


def test_endpoint_evaluate():
    r = client.post("/risk/evaluate", json={
        "id": "t9", "conta_origem": "c1", "chave_destino": "k1",
        "valor": 9000, "timestamp": "2026-10-22T03:00:00Z",
        "chave_criada_em": "2026-10-22T01:00:00Z",
    })
    assert r.status_code == 200
    assert r.json()["decisao"] == "BLOQUEADA"
