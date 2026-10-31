"""Servico de autorizacao (versao Python, provisoria ate a versao Java/Spring Boot).

Fluxo: le 'transacoes.pix' -> pergunta a engine de risco -> publica em 'decisoes.pix'.
Mensagens invalidas vao para 'transacoes.pix.dlq' (fila de mensagens com problema).
Se a engine estiver fora do ar, a transacao vai para EM_REVISAO (nunca aprova no escuro).
"""
import json
import os
import signal
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

TOPICO_ENTRADA = os.getenv("TOPIC_IN", "transacoes.pix")
TOPICO_SAIDA = os.getenv("TOPIC_OUT", "decisoes.pix")
TOPICO_DLQ = os.getenv("TOPIC_DLQ", "transacoes.pix.dlq")


class TransacaoInvalida(Exception):
    """A engine recusou a transacao (4xx): o problema esta na mensagem, nao na engine."""


def decidir(client: httpx.Client, tx: dict) -> dict:
    inicio = time.perf_counter()
    try:
        resp = client.post("/risk/evaluate", json=tx)
        if 400 <= resp.status_code < 500:
            raise TransacaoInvalida(f"engine respondeu {resp.status_code}")
        resp.raise_for_status()
        decisao = resp.json()
    except (httpx.HTTPError, ValueError):
        # Timeout, conexao recusada, 5xx ou resposta ilegivel: modo seguro.
        decisao = {
            "transacao_id": tx.get("id"),
            "decisao": "EM_REVISAO",
            "score": 0,
            "motivos": ["engine_indisponivel"],
        }
    latencia_ms = (time.perf_counter() - inicio) * 1000
    return {
        **decisao,
        "conta_origem": tx.get("conta_origem"),
        "valor": tx.get("valor"),
        "rotulo": tx.get("rotulo"),  # verdade conhecida do gerador (para metricas)
        "latencia_ms": round(latencia_ms, 1),
        "decidida_em": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def processar(client: httpx.Client, bruto: bytes) -> tuple[str, str | None, str]:
    """Transforma uma mensagem de entrada em (topico, chave, json) para publicar."""
    try:
        tx = json.loads(bruto)
    except ValueError:
        erro = {"erro": "json_invalido", "bruto": bruto.decode(errors="replace")[:500]}
        return TOPICO_DLQ, None, json.dumps(erro, ensure_ascii=False)

    if not isinstance(tx, dict):
        erro = {"erro": "formato_invalido", "bruto": str(tx)[:500]}
        return TOPICO_DLQ, None, json.dumps(erro, ensure_ascii=False)

    try:
        saida = decidir(client, tx)
    except TransacaoInvalida as e:
        erro = {"erro": "transacao_invalida", "detalhe": str(e), "transacao": tx}
        return TOPICO_DLQ, tx.get("conta_origem"), json.dumps(erro, ensure_ascii=False)

    return TOPICO_SAIDA, saida["conta_origem"], json.dumps(saida, ensure_ascii=False)


def criar_topicos(bootstrap: str) -> None:
    from confluent_kafka import KafkaException
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    novos = [
        NewTopic(TOPICO_ENTRADA, num_partitions=3, replication_factor=1),
        NewTopic(TOPICO_SAIDA, num_partitions=3, replication_factor=1),
        NewTopic(TOPICO_DLQ, num_partitions=1, replication_factor=1),
    ]
    for futuro in admin.create_topics(novos).values():
        try:
            futuro.result()
        except KafkaException as e:
            if "TOPIC_ALREADY_EXISTS" not in str(e):
                raise


def main() -> int:
    from confluent_kafka import Consumer, Producer

    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    engine_url = os.getenv("ENGINE_URL", "http://localhost:8000")
    criar_topicos(bootstrap)

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": os.getenv("GROUP_ID", "authorization-worker"),
        # 'latest': so processa transacoes novas. Use 'earliest' para reprocessar o historico.
        "auto.offset.reset": os.getenv("AUTO_OFFSET_RESET", "latest"),
        "enable.auto.commit": False,
    })
    producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 5})
    client = httpx.Client(base_url=engine_url, timeout=httpx.Timeout(1.0))
    consumer.subscribe([TOPICO_ENTRADA])

    rodando = True

    def parar(*_):
        nonlocal rodando
        rodando = False

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)

    print(f"Consumindo '{TOPICO_ENTRADA}' -> publicando em '{TOPICO_SAIDA}' (engine: {engine_url})", flush=True)
    contagem: Counter = Counter()
    try:
        while rodando:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Erro do Kafka: {msg.error()}", file=sys.stderr, flush=True)
                continue

            topico, chave, payload = processar(client, msg.value())
            producer.produce(topico, key=chave, value=payload)
            producer.poll(0)
            consumer.commit(message=msg, asynchronous=True)

            contagem["dlq" if topico == TOPICO_DLQ else json.loads(payload)["decisao"]] += 1
            if sum(contagem.values()) % 20 == 0:
                print(f"Decisoes: {dict(contagem)}", flush=True)
    finally:
        producer.flush(5)
        consumer.close()
        client.close()
        print(f"Encerrado. Total: {dict(contagem)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
