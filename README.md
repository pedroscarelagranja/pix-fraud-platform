# PIX Fraud Platform

Plataforma de detecção de fraude no PIX em tempo real (projeto de portfólio).
Recebe um fluxo de transações PIX **simuladas**, avalia o risco de cada uma em milissegundos
e decide: `APROVADA`, `EM_REVISAO` ou `BLOQUEADA`.

> Status: em construção 🚧

## Arquitetura

Veja [docs/architecture.md](docs/architecture.md).

| Componente | Tecnologia | Papel |
|---|---|---|
| tx-generator | Python | Simula transações (inclui golpes) |
| authorization-worker | Python (provisório) | Lê o Kafka, consulta a engine e publica a decisão |
| authorization-service | Java, Spring Boot | Versão final do serviço de autorização |
| risk-engine | Python, FastAPI | Regras antifraude e score de risco |
| Mensageria | Kafka | Ingestão e eventos |
| Dados | PostgreSQL, Redis | Histórico e perfil do usuário |

## Como rodar (local, 100% gratuito)

```bash
# infraestrutura
docker compose up -d

# risk-engine
cd risk-engine
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# docs interativas: http://localhost:8000/docs
```

Testes (na raiz do repositório): `pytest`

### Pipeline completo (tudo em containers)

```bash
docker compose up -d --build                 # infra + risk-engine + authorization-worker
docker compose up -d --build tx-generator    # começa a gerar transações
docker compose logs -f authorization-worker  # decisões em tempo real
```

As decisões aparecem no tópico `decisoes.pix` (Kafka UI em http://localhost:8080).
Mensagens inválidas vão para `transacoes.pix.dlq`.

### Métricas

```bash
docker compose run --rm metrics    # lê decisoes.pix e gera docs/metricas.md
```

Compara cada decisão com o `rotulo` (verdade conhecida do gerador) e mostra taxa de detecção
por tipo de golpe, falsos positivos, precisão e latência (p50/p95/p99).

### Gerador de transações simuladas

```bash
# só imprime 10 lotes (precisa apenas do Python)
python tx-generator/generator.py --dry-run --count 10

# publica no Kafka (via Docker); acompanhe em http://localhost:8080
docker compose up -d --build tx-generator
docker compose logs -f tx-generator
docker compose stop tx-generator
```

Cenários de golpe simulados: valor muito alto para chave nova, madrugada com chave recente
e rajada de transferências. Cada mensagem leva um campo `rotulo` (a verdade conhecida),
usado depois para medir acertos e falsos positivos.

## Regras iniciais

- valor alto (>= R$ 5.000)
- horário atípico (madrugada)
- chave PIX criada há menos de 24h
- valor fora do hábito do usuário (> 5x a média, após 5 transações) — perfil no Redis
- transferências em sequência (3+ tentativas em 60s)

## Roadmap

- [x] Infra local (Kafka, Postgres, Redis)
- [x] risk-engine com regras básicas e testes
- [x] Perfil do usuário no Redis (valor fora do hábito e transferências em sequência)
- [x] tx-generator publicando no Kafka
- [x] authorization-worker em Python (transacoes.pix → engine → decisoes.pix)
- [ ] authorization-service (Spring Boot), substituindo o worker
- [x] Relatório de métricas (detecção, falsos positivos, latência p95) em [docs/metricas.md](docs/metricas.md)
- [ ] Modelo de anomalia (Isolation Forest)
