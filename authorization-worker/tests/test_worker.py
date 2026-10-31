import json

import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.profile import PerfilStore
from worker import TOPICO_DLQ, TOPICO_SAIDA, TransacaoInvalida, decidir, processar

TX = {
    "id": "t1", "conta_origem": "conta-1", "chave_destino": "k1", "valor": 100,
    "timestamp": "2026-10-30T15:00:00Z", "rotulo": "normal",
}


def _cliente(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://engine")


def _ok(request):
    return httpx.Response(200, json={
        "transacao_id": "t1", "decisao": "APROVADA", "score": 0, "motivos": []})


def test_decidir_monta_a_saida():
    saida = decidir(_cliente(_ok), TX)
    assert saida["decisao"] == "APROVADA"
    assert saida["conta_origem"] == "conta-1" and saida["rotulo"] == "normal"
    assert saida["latencia_ms"] >= 0 and saida["decidida_em"].endswith("Z")


def test_engine_com_erro_500_vai_para_revisao():
    saida = decidir(_cliente(lambda r: httpx.Response(503)), TX)
    assert saida["decisao"] == "EM_REVISAO" and saida["motivos"] == ["engine_indisponivel"]


def test_engine_fora_do_ar_vai_para_revisao():
    def fora(request):
        raise httpx.ConnectError("recusou")

    saida = decidir(_cliente(fora), TX)
    assert saida["decisao"] == "EM_REVISAO"


def test_transacao_recusada_pela_engine_levanta_erro():
    with pytest.raises(TransacaoInvalida):
        decidir(_cliente(lambda r: httpx.Response(422)), TX)


def test_processar_publica_em_decisoes():
    topico, chave, payload = processar(_cliente(_ok), json.dumps(TX).encode())
    assert topico == TOPICO_SAIDA and chave == "conta-1"
    assert json.loads(payload)["decisao"] == "APROVADA"


def test_json_quebrado_vai_para_dlq():
    topico, _, payload = processar(_cliente(_ok), b"{isso nao e json")
    assert topico == TOPICO_DLQ and json.loads(payload)["erro"] == "json_invalido"


def test_json_que_nao_e_objeto_vai_para_dlq():
    topico, _, payload = processar(_cliente(_ok), b"[1, 2, 3]")
    assert topico == TOPICO_DLQ and json.loads(payload)["erro"] == "formato_invalido"


def test_transacao_invalida_vai_para_dlq():
    topico, _, payload = processar(_cliente(lambda r: httpx.Response(422)), json.dumps(TX).encode())
    assert topico == TOPICO_DLQ and json.loads(payload)["erro"] == "transacao_invalida"


def test_integracao_com_a_engine_real():
    """Worker + engine de verdade (sem rede), com Redis falso: golpe tem que ser bloqueado."""
    store = PerfilStore(fakeredis.FakeRedis(decode_responses=True))
    app.dependency_overrides[get_store] = lambda: store
    try:
        golpe = {**TX, "valor": 9000, "chave_criada_em": "2026-10-30T14:00:00Z", "rotulo": "golpe_valor_alto"}
        topico, _, payload = processar(TestClient(app), json.dumps(golpe).encode())
    finally:
        app.dependency_overrides.clear()
    saida = json.loads(payload)
    assert topico == TOPICO_SAIDA
    assert saida["decisao"] == "BLOQUEADA" and saida["rotulo"] == "golpe_valor_alto"
