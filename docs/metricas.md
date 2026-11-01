# Métricas do sistema antifraude

_Gerado em 01/11/2026 00:36 UTC a partir de 552 decisões simuladas. Os dados vêm do gerador e as regras são iniciais: os números não representam um cenário real._

## Resumo

| Métrica | Valor |
|---|---|
| Transações normais | 387 |
| Golpes simulados | 165 |
| Taxa de detecção (bloqueado ou em revisão) | 100.0% |
| Golpes bloqueados direto | 81.8% |
| Falsos positivos (normal bloqueada) | 0 (0.0%) |
| Normais enviadas para revisão | 0 (0.0%) |
| Precisão dos alertas (alertas que eram golpe) | 100.0% |

## Por tipo de golpe

| Tipo | Total | Bloqueadas | Em revisão | Escaparam (aprovadas) | Detecção |
|---|---|---|---|---|---|
| golpe_madrugada | 27 | 21 | 6 | 0 | 100.0% |
| golpe_rajada | 115 | 91 | 24 | 0 | 100.0% |
| golpe_valor_alto | 23 | 23 | 0 | 0 | 100.0% |

## Latência da consulta à engine (ms)

| p50 | p95 | p99 | máx |
|---|---|---|---|
| 2.7 | 3.6 | 4.1 | 14.0 |

## Motivos mais frequentes

| Motivo | Ocorrências |
|---|---|
| transferencias_em_sequencia | 265 |
| chave_recente | 165 |
| valor_fora_do_habito | 28 |
| horario_atipico | 27 |
| valor_alto | 23 |
