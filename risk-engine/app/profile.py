import redis

from .schemas import PerfilUsuario


class PerfilStore:
    """Guarda no Redis o perfil de cada conta e conta tentativas recentes.

    O cliente precisa ser criado com decode_responses=True.
    """

    def __init__(self, client: redis.Redis, janela_rajada_s: int = 60):
        self.r = client
        self.janela_rajada_s = janela_rajada_s

    @staticmethod
    def _chave_perfil(conta: str) -> str:
        return f"perfil:{conta}"

    @staticmethod
    def _chave_rajada(conta: str) -> str:
        return f"rajada:{conta}"

    def obter(self, conta: str) -> PerfilUsuario:
        dados = self.r.hgetall(self._chave_perfil(conta))
        if not dados:
            return PerfilUsuario()
        return PerfilUsuario(qtd=int(dados["qtd"]), media=float(dados["media"]))

    def atualizar(self, conta: str, valor: float) -> None:
        """Atualiza a media de forma incremental (sem guardar o historico todo).

        Obs.: le e escreve em dois passos, entao duas transacoes simultaneas da mesma
        conta podem se atropelar. Evolucao futura: script Lua ou transacao no Redis.
        """
        atual = self.obter(conta)
        nova_qtd = atual.qtd + 1
        nova_media = atual.media + (valor - atual.media) / nova_qtd
        self.r.hset(self._chave_perfil(conta), mapping={"qtd": nova_qtd, "media": nova_media})

    def registrar_tentativa(self, conta: str) -> int:
        """Conta quantas tentativas a conta fez na janela atual (inclui a de agora)."""
        chave = self._chave_rajada(conta)
        total = int(self.r.incr(chave))
        if total == 1:
            self.r.expire(chave, self.janela_rajada_s)
        return total
