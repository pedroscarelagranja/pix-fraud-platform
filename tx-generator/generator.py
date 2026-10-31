"""Gerador de transacoes PIX simuladas.

Publica no Kafka (topico transacoes.pix) um fluxo de transacoes normais misturadas
com cenarios de golpe. Cada mensagem traz o campo extra "rotulo" (verdade conhecida),
que a engine ignora, mas permite medir acertos e falsos positivos depois.

Uso:
  python generator.py --dry-run --count 10     # so imprime, sem Kafka
  python generator.py                          # publica no Kafka (Ctrl+C para parar)
"""
import argparse
import json
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")
TOPICO = os.getenv("TOPIC", "transacoes.pix")


@dataclass(frozen=True)
class Conta:
    id: str
    habito: float  # valor tipico das transferencias dessa conta


CONTAS = [Conta(f"conta-{i:03d}", round(random.Random(i).uniform(40, 400), 2)) for i in range(1, 51)]
CHAVES_ANTIGAS = [f"chave-{i:04d}" for i in range(1, 201)]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _tx(conta: Conta, valor: float, ts: datetime, chave: str,
        chave_criada_em: datetime | None, rotulo: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "conta_origem": conta.id,
        "chave_destino": chave,
        "valor": round(valor, 2),
        "timestamp": iso(ts),
        "chave_criada_em": iso(chave_criada_em) if chave_criada_em else None,
        "rotulo": rotulo,
    }


def normal(rng: random.Random) -> list[dict]:
    conta = rng.choice(CONTAS)
    ts = agora()
    criada = ts - timedelta(days=rng.randint(30, 900))
    valor = conta.habito * rng.uniform(0.5, 1.6)
    return [_tx(conta, valor, ts, rng.choice(CHAVES_ANTIGAS), criada, "normal")]


def golpe_valor_alto(rng: random.Random) -> list[dict]:
    conta = rng.choice(CONTAS)
    ts = agora()
    valor = max(5000.0, conta.habito * rng.uniform(15, 40))
    criada = ts - timedelta(hours=rng.randint(1, 6))
    return [_tx(conta, valor, ts, f"chave-nova-{uuid.uuid4().hex[:6]}", criada, "golpe_valor_alto")]


def golpe_madrugada(rng: random.Random) -> list[dict]:
    conta = rng.choice(CONTAS)
    local = agora().astimezone(FUSO_BRASIL).replace(
        hour=rng.randint(1, 4), minute=rng.randint(0, 59), second=0, microsecond=0)
    ts = local.astimezone(timezone.utc)
    valor = rng.uniform(2000, 4500)  # abaixo do limite de "valor alto" de proposito
    criada = ts - timedelta(hours=rng.randint(1, 5))
    return [_tx(conta, valor, ts, f"chave-nova-{uuid.uuid4().hex[:6]}", criada, "golpe_madrugada")]


def golpe_rajada(rng: random.Random) -> list[dict]:
    conta = rng.choice(CONTAS)
    ts = agora()
    chave = f"chave-nova-{uuid.uuid4().hex[:6]}"
    criada = ts - timedelta(hours=1)
    return [_tx(conta, conta.habito * rng.uniform(1.0, 2.5), ts, chave, criada, "golpe_rajada")
            for _ in range(5)]


GOLPES = [golpe_valor_alto, golpe_madrugada, golpe_rajada]


def proximo_lote(rng: random.Random, taxa_golpe: float) -> list[dict]:
    if rng.random() < taxa_golpe:
        return rng.choice(GOLPES)(rng)
    return normal(rng)


def criar_topico(bootstrap: str) -> None:
    from confluent_kafka import KafkaException
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    for futuro in admin.create_topics([NewTopic(TOPICO, num_partitions=3, replication_factor=1)]).values():
        try:
            futuro.result()
        except KafkaException as e:
            if "TOPIC_ALREADY_EXISTS" not in str(e):
                raise


def main() -> int:
    ap = argparse.ArgumentParser(description="Gerador de transacoes PIX simuladas")
    ap.add_argument("--dry-run", action="store_true", help="imprime as transacoes sem enviar ao Kafka")
    ap.add_argument("--count", type=int, default=0, help="quantos lotes gerar (0 = infinito)")
    ap.add_argument("--rate", type=float, default=float(os.getenv("RATE_PER_SEC", "2")),
                    help="lotes por segundo")
    ap.add_argument("--fraud-ratio", type=float, default=float(os.getenv("FRAUD_RATIO", "0.15")),
                    help="proporcao de lotes que sao golpes (0 a 1)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    producer = None
    if not args.dry_run:
        from confluent_kafka import Producer

        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
        criar_topico(bootstrap)
        producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 20})
        print(f"Publicando em '{TOPICO}' via {bootstrap} (Ctrl+C para parar)", flush=True)

    enviados = 0
    lotes = 0
    try:
        while args.count == 0 or lotes < args.count:
            for tx in proximo_lote(rng, args.fraud_ratio):
                payload = json.dumps(tx, ensure_ascii=False)
                if producer:
                    producer.produce(TOPICO, key=tx["conta_origem"], value=payload)
                    producer.poll(0)
                else:
                    print(payload)
                enviados += 1
            lotes += 1
            if producer and lotes % 20 == 0:
                print(f"{enviados} transacoes enviadas", flush=True)
            time.sleep(1 / args.rate if args.rate > 0 else 0)
    except KeyboardInterrupt:
        pass
    finally:
        if producer:
            producer.flush(5)
    print(f"Fim: {enviados} transacoes geradas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
