-- Executado automaticamente na primeira subida do Postgres

CREATE TABLE IF NOT EXISTS transacoes (
    id              TEXT PRIMARY KEY,
    conta_origem    TEXT        NOT NULL,
    chave_destino   TEXT        NOT NULL,
    valor           NUMERIC(14,2) NOT NULL CHECK (valor > 0),
    ocorrida_em     TIMESTAMPTZ NOT NULL,
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisoes (
    id              BIGSERIAL PRIMARY KEY,
    transacao_id    TEXT        NOT NULL REFERENCES transacoes(id),
    decisao         TEXT        NOT NULL CHECK (decisao IN ('APROVADA','EM_REVISAO','BLOQUEADA')),
    score           INTEGER     NOT NULL,
    motivos         TEXT[]      NOT NULL DEFAULT '{}',
    decidida_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transacoes_conta_data ON transacoes (conta_origem, ocorrida_em DESC);
CREATE INDEX IF NOT EXISTS idx_decisoes_transacao ON decisoes (transacao_id);
