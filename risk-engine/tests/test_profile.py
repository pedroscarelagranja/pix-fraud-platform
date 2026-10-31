import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.profile import PerfilStore
from app.rules import avaliar
from app.schemas import PerfilUsuario, Transacao

MEIO_DIA = "2026-10-30T15:00:00Z"  # 12:00 em Brasilia


@pytest.fixture
def store():
    return PerfilStore(fakeredis.FakeRedis(decode_responses=True))


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(**kw):
    base = {
        "id": "t1", "conta_origem": "conta-1", "chave_destino": "k1",
        "valor": 100, "timestamp": MEIO_DIA,
    }
    base.update(kw)
    return base


def test_media_incremental(store):
    store.atualizar("c1", 100)
    store.atualizar("c1", 200)
    perfil = store.obter("c1")
    assert perfil.qtd == 2 and perfil.media == pytest.approx(150)


def test_conta_sem_historico_tem_perfil_vazio(store):
    assert store.obter("nova") == PerfilUsuario()


def test_valor_fora_do_habito_na_regra():
    tx = Transacao(**_payload(valor=1000))
    d = avaliar(tx, PerfilUsuario(qtd=10, media=100))
    assert "valor_fora_do_habito" in d.motivos and d.decisao == "EM_REVISAO"


def test_sem_historico_suficiente_nao_dispara_fora_do_habito():
    tx = Transacao(**_payload(valor=1000))
    d = avaliar(tx, PerfilUsuario(qtd=2, media=100))
    assert "valor_fora_do_habito" not in d.motivos


def test_endpoint_usa_perfil_do_redis(client, store):
    for _ in range(5):
        store.atualizar("conta-1", 100)
    r = client.post("/risk/evaluate", json=_payload(valor=1000))
    assert r.json()["decisao"] == "EM_REVISAO"
    assert "valor_fora_do_habito" in r.json()["motivos"]


def test_rajada_de_transferencias(client):
    motivos = []
    for i in range(3):
        r = client.post("/risk/evaluate", json=_payload(id=f"t{i}"))
        motivos = r.json()["motivos"]
    assert "transferencias_em_sequencia" in motivos


def test_transacao_bloqueada_nao_atualiza_perfil(client, store):
    r = client.post("/risk/evaluate", json=_payload(
        valor=9000, chave_criada_em="2026-10-30T14:00:00Z"))
    assert r.json()["decisao"] == "BLOQUEADA"
    assert store.obter("conta-1").qtd == 0


def test_transacao_aprovada_atualiza_perfil(client, store):
    client.post("/risk/evaluate", json=_payload(valor=250))
    assert store.obter("conta-1").qtd == 1


def test_redis_fora_do_ar_nao_derruba_a_engine(client):
    class StoreQuebrado:
        def registrar_tentativa(self, conta):
            raise redis.ConnectionError("fora do ar")

        def obter(self, conta):
            raise redis.ConnectionError("fora do ar")

        def atualizar(self, conta, valor):
            raise redis.ConnectionError("fora do ar")

    app.dependency_overrides[get_store] = lambda: StoreQuebrado()
    r = client.post("/risk/evaluate", json=_payload())
    assert r.status_code == 200 and r.json()["decisao"] == "APROVADA"
