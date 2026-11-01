"""Relatorio de metricas do sistema antifraude.

Le todas as decisoes de 'decisoes.pix' e compara cada uma com o 'rotulo' (a verdade
conhecida, colocada pelo gerador): mede quantos golpes foram pegos, quantas transacoes
normais foram barradas por engano (falsos positivos) e a latencia da engine.

Uso (via Docker):  docker compose run --rm metrics
"""
import argparse
import json
import math
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone


def pct(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def percentil(ordenados: list[float], p: float) -> float:
    """Percentil pelo metodo 'nearest-rank'. A lista precisa estar ordenada."""
    if not ordenados:
        return 0.0
    i = max(math.ceil(p / 100 * len(ordenados)) - 1, 0)
    return ordenados[i]


def _contar(lista: list[dict], decisao: str) -> int:
    return sum(1 for d in lista if d.get("decisao") == decisao)


def calcular(decisoes: list[dict]) -> dict:
    com_rotulo = [d for d in decisoes if d.get("rotulo")]
    normais = [d for d in com_rotulo if d["rotulo"] == "normal"]
    golpes = [d for d in com_rotulo if d["rotulo"] != "normal"]

    por_tipo = {}
    for tipo in sorted({d["rotulo"] for d in golpes}):
        grupo = [d for d in golpes if d["rotulo"] == tipo]
        bloq, rev, apr = (_contar(grupo, x) for x in ("BLOQUEADA", "EM_REVISAO", "APROVADA"))
        por_tipo[tipo] = {
            "total": len(grupo), "bloqueadas": bloq, "em_revisao": rev, "aprovadas": apr,
            "deteccao": pct(bloq + rev, len(grupo)),
        }

    g_bloq, g_rev = _contar(golpes, "BLOQUEADA"), _contar(golpes, "EM_REVISAO")
    n_bloq, n_rev = _contar(normais, "BLOQUEADA"), _contar(normais, "EM_REVISAO")
    alertas = g_bloq + g_rev + n_bloq + n_rev

    latencias = sorted(d["latencia_ms"] for d in decisoes if isinstance(d.get("latencia_ms"), (int, float)))
    motivos = Counter(m for d in decisoes for m in d.get("motivos", []))

    return {
        "total": len(decisoes),
        "sem_rotulo": len(decisoes) - len(com_rotulo),
        "normais": len(normais),
        "golpes": len(golpes),
        "deteccao": pct(g_bloq + g_rev, len(golpes)),
        "bloqueio_direto": pct(g_bloq, len(golpes)),
        "falsos_positivos_bloqueio": n_bloq,
        "falsos_positivos_bloqueio_pct": pct(n_bloq, len(normais)),
        "normais_em_revisao": n_rev,
        "normais_em_revisao_pct": pct(n_rev, len(normais)),
        "precisao": pct(g_bloq + g_rev, alertas),
        "por_tipo": por_tipo,
        "latencia": {
            "p50": percentil(latencias, 50), "p95": percentil(latencias, 95),
            "p99": percentil(latencias, 99), "max": latencias[-1] if latencias else 0.0,
        },
        "motivos": motivos.most_common(),
        "engine_indisponivel": motivos.get("engine_indisponivel", 0),
    }


def formatar_markdown(r: dict, gerado_em: datetime | None = None) -> str:
    quando = (gerado_em or datetime.now(timezone.utc)).strftime("%d/%m/%Y %H:%M UTC")
    linhas = [
        "# Métricas do sistema antifraude",
        "",
        f"_Gerado em {quando} a partir de {r['total']} decisões simuladas. "
        "Os dados vêm do gerador e as regras são iniciais: os números não representam um cenário real._",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Transações normais | {r['normais']} |",
        f"| Golpes simulados | {r['golpes']} |",
        f"| Taxa de detecção (bloqueado ou em revisão) | {r['deteccao']}% |",
        f"| Golpes bloqueados direto | {r['bloqueio_direto']}% |",
        f"| Falsos positivos (normal bloqueada) | {r['falsos_positivos_bloqueio']} ({r['falsos_positivos_bloqueio_pct']}%) |",
        f"| Normais enviadas para revisão | {r['normais_em_revisao']} ({r['normais_em_revisao_pct']}%) |",
        f"| Precisão dos alertas (alertas que eram golpe) | {r['precisao']}% |",
        "",
        "## Por tipo de golpe",
        "",
        "| Tipo | Total | Bloqueadas | Em revisão | Escaparam (aprovadas) | Detecção |",
        "|---|---|---|---|---|---|",
    ]
    for tipo, v in r["por_tipo"].items():
        linhas.append(
            f"| {tipo} | {v['total']} | {v['bloqueadas']} | {v['em_revisao']} | {v['aprovadas']} | {v['deteccao']}% |")
    lat = r["latencia"]
    linhas += [
        "",
        "## Latência da consulta à engine (ms)",
        "",
        "| p50 | p95 | p99 | máx |",
        "|---|---|---|---|",
        f"| {lat['p50']} | {lat['p95']} | {lat['p99']} | {lat['max']} |",
        "",
        "## Motivos mais frequentes",
        "",
        "| Motivo | Ocorrências |",
        "|---|---|",
    ]
    linhas += [f"| {m} | {n} |" for m, n in r["motivos"]]
    if r["engine_indisponivel"]:
        linhas += ["", f"> Atenção: {r['engine_indisponivel']} decisões foram tomadas com a engine indisponível."]
    if r["sem_rotulo"]:
        linhas += ["", f"> {r['sem_rotulo']} decisões sem rótulo foram ignoradas nas taxas."]
    return "\n".join(linhas) + "\n"


def ler_decisoes(bootstrap: str, topico: str) -> list[dict]:
    """Le o topico inteiro, do comeco ate o fim de cada particao, sem usar grupo/offsets."""
    from confluent_kafka import OFFSET_BEGINNING, Consumer, TopicPartition

    c = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"metrics-{uuid.uuid4()}",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    meta = c.list_topics(topico, timeout=10).topics.get(topico)
    if meta is None or meta.error:
        raise SystemExit(f"Topico '{topico}' nao encontrado. Rode o gerador antes.")

    particoes = list(meta.partitions)
    c.assign([TopicPartition(topico, p, OFFSET_BEGINNING) for p in particoes])
    fim, pendentes = {}, set()
    for p in particoes:
        baixo, alto = c.get_watermark_offsets(TopicPartition(topico, p), timeout=10)
        fim[p] = alto
        if alto > baixo:
            pendentes.add(p)

    decisoes, vazios = [], 0
    while pendentes and vazios < 10:
        msg = c.poll(1.0)
        if msg is None:
            vazios += 1
            continue
        vazios = 0
        if msg.error():
            continue
        try:
            decisoes.append(json.loads(msg.value()))
        except ValueError:
            pass
        if msg.offset() >= fim[msg.partition()] - 1:
            pendentes.discard(msg.partition())
    c.close()
    return decisoes


def main() -> int:
    ap = argparse.ArgumentParser(description="Metricas do sistema antifraude PIX")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"))
    ap.add_argument("--topic", default=os.getenv("TOPIC_DECISOES", "decisoes.pix"))
    ap.add_argument("--out", default=None, help="caminho para salvar o relatorio em Markdown")
    args = ap.parse_args()

    decisoes = ler_decisoes(args.bootstrap, args.topic)
    if not decisoes:
        print("Nenhuma decisao encontrada. Ligue o gerador e o worker e tente de novo.", file=sys.stderr)
        return 1
    texto = formatar_markdown(calcular(decisoes))
    print(texto)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"Relatorio salvo em {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
