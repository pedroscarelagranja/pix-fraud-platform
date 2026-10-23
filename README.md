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

## Regras iniciais

- valor alto (>= R$ 5.000)
- horário atípico (madrugada)
- chave PIX criada há menos de 24h
- (próximas) transferências em sequência, valor fora do hábito do usuário

## Roadmap

- [x] Infra local (Kafka, Postgres, Redis)
- [x] risk-engine com regras básicas e testes
- [ ] Perfil do usuário no Redis
- [ ] tx-generator publicando no Kafka
- [ ] authorization-service (Spring Boot)
- [ ] Métricas (latência p95, taxa de bloqueio, falsos positivos)
- [ ] Modelo de anomalia (Isolation Forest)
