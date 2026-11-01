from report import calcular, formatar_markdown, percentil


def _d(rotulo, decisao, lat=5.0, motivos=()):
    return {"rotulo": rotulo, "decisao": decisao, "latencia_ms": lat, "motivos": list(motivos)}


DECISOES = (
    [_d("normal", "APROVADA")] * 7
    + [_d("normal", "EM_REVISAO", motivos=["horario_atipico"])]
    + [_d("golpe_valor_alto", "BLOQUEADA", motivos=["valor_alto"])] * 3
    + [_d("golpe_valor_alto", "APROVADA")]
    + [_d("golpe_rajada", "EM_REVISAO")] * 2
    + [{"decisao": "APROVADA", "latencia_ms": 1.0, "motivos": []}]  # sem rotulo
)


def test_contagens_e_taxas():
    r = calcular(DECISOES)
    assert r["normais"] == 8 and r["golpes"] == 6 and r["sem_rotulo"] == 1
    assert r["deteccao"] == 83.3          # 5 de 6 golpes pegos
    assert r["bloqueio_direto"] == 50.0   # 3 de 6 bloqueados
    assert r["normais_em_revisao"] == 1 and r["normais_em_revisao_pct"] == 12.5
    assert r["falsos_positivos_bloqueio"] == 0
    assert r["precisao"] == 83.3          # 5 alertas de golpe em 6 alertas


def test_por_tipo():
    t = calcular(DECISOES)["por_tipo"]
    assert t["golpe_valor_alto"]["deteccao"] == 75.0 and t["golpe_valor_alto"]["aprovadas"] == 1
    assert t["golpe_rajada"]["deteccao"] == 100.0


def test_percentil():
    assert percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert percentil([], 95) == 0.0


def test_sem_golpes_nao_divide_por_zero():
    r = calcular([_d("normal", "APROVADA")])
    assert r["golpes"] == 0 and r["deteccao"] == 0.0 and r["precisao"] == 0.0


def test_markdown_tem_as_secoes_e_numeros():
    md = formatar_markdown(calcular(DECISOES))
    for trecho in ("# Métricas do sistema antifraude", "## Por tipo de golpe", "golpe_valor_alto", "83.3%"):
        assert trecho in md
