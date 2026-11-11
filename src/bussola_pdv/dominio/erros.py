"""Hierarquia de erros do domínio.

Regra do projeto: nenhuma camada superior deve precisar inspecionar mensagens de
texto para decidir o que fazer. Cada erro carrega um `codigo` estável, que a UI
usa para escolher a mensagem ao operador e a aplicação usa para auditoria.
"""

from __future__ import annotations


class ErroBussola(Exception):
    """Base de todos os erros tratados da aplicação."""

    codigo = "ERRO_GENERICO"

    def __init__(self, mensagem: str, *, codigo: str | None = None, detalhe: dict | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo or type(self).codigo
        self.detalhe = detalhe or {}

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.mensagem


class ErroValidacao(ErroBussola):
    codigo = "VALIDACAO"


class ErroNaoEncontrado(ErroBussola):
    codigo = "NAO_ENCONTRADO"


class ErroConflito(ErroBussola):
    """Violação de unicidade, idempotência ou corrida entre transações."""

    codigo = "CONFLITO"


# --- Autenticação e autorização ------------------------------------------------


class CredenciaisInvalidas(ErroBussola):
    codigo = "CREDENCIAIS_INVALIDAS"


class UsuarioBloqueado(ErroBussola):
    codigo = "USUARIO_BLOQUEADO"


class AutorizacaoNegada(ErroBussola):
    codigo = "AUTORIZACAO_NEGADA"


# --- Venda e pagamento ---------------------------------------------------------


class CarrinhoVazio(ErroValidacao):
    codigo = "CARRINHO_VAZIO"


class EstoqueInsuficiente(ErroValidacao):
    codigo = "ESTOQUE_INSUFICIENTE"


class PagamentoIncompleto(ErroValidacao):
    codigo = "PAGAMENTO_INCOMPLETO"

    def __init__(self, mensagem: str, *, falta_centavos: int = 0) -> None:
        super().__init__(mensagem, detalhe={"falta_centavos": falta_centavos})
        self.falta_centavos = falta_centavos


class PagamentoInvalido(ErroValidacao):
    codigo = "PAGAMENTO_INVALIDO"


class TrocoInvalido(PagamentoInvalido):
    codigo = "TROCO_INVALIDO"


class VendaJaFinalizada(ErroConflito):
    codigo = "VENDA_JA_FINALIZADA"


# --- Caixa e turno -------------------------------------------------------------


class TurnoNaoAberto(ErroBussola):
    codigo = "TURNO_NAO_ABERTO"


class TurnoJaAberto(ErroConflito):
    codigo = "TURNO_JA_ABERTO"


class TurnoJaFechado(ErroConflito):
    codigo = "TURNO_JA_FECHADO"


# --- Crediário -----------------------------------------------------------------


class LimiteCreditoExcedido(ErroValidacao):
    codigo = "LIMITE_CREDITO_EXCEDIDO"


class ClienteBloqueadoPorAtraso(ErroValidacao):
    codigo = "CLIENTE_BLOQUEADO_ATRASO"


class RecebimentoInvalido(ErroValidacao):
    codigo = "RECEBIMENTO_INVALIDO"
