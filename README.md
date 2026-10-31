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
| authorization-service | Java, Spring Boot | Autoriza/bloqueia a transação |
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
- [ ] authorization-service (Spring Boot)
- [ ] Métricas (latência p95, taxa de bloqueio, falsos positivos)
- [ ] Modelo de anomalia (Isolation Forest)
