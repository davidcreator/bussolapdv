"""Usuários, hierarquia de cinco perfis e permissões explícitas por ação.

Três invariantes sustentam este módulo:

1. **Perfil não é cargo decorativo.** Cada ação sensível tem nome próprio e a
   autorização de desconto, sangria, estoque negativo, cancelamento e ajuste
   exige **autenticação do autorizador**, não o nome digitado.
2. **Nível hierárquico é comparável.** Um usuário só gerencia quem está
   *estritamente* abaixo dele; ninguém altera o próprio perfil nem o próprio
   acesso. Isso impede promoção silenciosa e "conta que se reativa sozinha".
3. **O Admin Master não pode ser trancado para fora.** Ele tem acesso integral
   por definição de código — não existe tabela que possa revogar isso — e há no
   máximo um master ativo por instalação (garantido também por índice no banco).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .erros import AutorizacaoNegada, ErroValidacao


class Perfil(StrEnum):
    """Cinco perfis, do operacional ao proprietário da instalação."""

    ATENDENTE = "ATENDENTE"
    GERENTE = "GERENTE"
    CONTABILIDADE = "CONTABILIDADE"
    ADMIN = "ADMIN"
    ADMIN_MASTER = "ADMIN_MASTER"

    # -- aliases legados ----------------------------------------------------
    # Bancos criados nas versões 1 e 2 usavam OPERADOR/ADMINISTRADOR. Os nomes
    # continuam válidos como alias para não quebrar código antigo; a migração
    # 0003 converte os valores gravados.
    OPERADOR = "ATENDENTE"
    ADMINISTRADOR = "ADMIN"

    @property
    def nivel(self) -> int:
        """Hierarquia: quem tem número maior pode gerenciar quem tem menor."""
        return {
            Perfil.ATENDENTE: 20,
            Perfil.CONTABILIDADE: 30,
            Perfil.GERENTE: 40,
            Perfil.ADMIN: 70,
            Perfil.ADMIN_MASTER: 100,
        }[self]

    @property
    def rotulo(self) -> str:
        return {
            Perfil.ATENDENTE: "Atendente",
            Perfil.GERENTE: "Gerente",
            Perfil.CONTABILIDADE: "Contabilidade",
            Perfil.ADMIN: "Admin",
            Perfil.ADMIN_MASTER: "Admin Master",
        }[self]

    @property
    def descricao(self) -> str:
        return {
            Perfil.ATENDENTE: "Opera o PDV e o próprio turno de caixa. Sem cadastros nem exceções.",
            Perfil.GERENTE: "Supervisiona a loja: exceções, cadastros, estoque, cancelamentos e caixa.",
            Perfil.CONTABILIDADE: "Acesso somente de leitura a relatórios, fechamentos e auditoria.",
            Perfil.ADMIN: "Administra a instalação, os usuários e o conteúdo — conforme o master liberar.",
            Perfil.ADMIN_MASTER: "Proprietário da instalação: define o que cada perfil pode fazer.",
        }[self]

    @property
    def eh_master(self) -> bool:
        return self is Perfil.ADMIN_MASTER


class CategoriaAcao(StrEnum):
    """Agrupamento usado na matriz de permissões da área administrativa."""

    VENDAS = "VENDAS"
    CAIXA = "CAIXA"
    CADASTROS = "CADASTROS"
    ESTOQUE = "ESTOQUE"
    FINANCEIRO = "FINANCEIRO"
    ADMINISTRACAO = "ADMINISTRACAO"

    @property
    def rotulo(self) -> str:
        return {
            CategoriaAcao.VENDAS: "Vendas e PDV",
            CategoriaAcao.CAIXA: "Caixa",
            CategoriaAcao.CADASTROS: "Cadastros",
            CategoriaAcao.ESTOQUE: "Estoque",
            CategoriaAcao.FINANCEIRO: "Financeiro e relatórios",
            CategoriaAcao.ADMINISTRACAO: "Administração",
        }[self]

    @property
    def ordem(self) -> int:
        return list(CategoriaAcao).index(self)


class Acao(StrEnum):
    """Permissões nomeadas. Toda regra sensível referencia uma destas."""

    # Vendas / PDV
    PDV_VENDER = "PDV_VENDER"
    PDV_DESCONTO_ITEM = "PDV_DESCONTO_ITEM"
    PDV_DESCONTO_EXCEPCIONAL = "PDV_DESCONTO_EXCEPCIONAL"
    PDV_VENDA_ESTOQUE_NEGATIVO = "PDV_VENDA_ESTOQUE_NEGATIVO"
    PDV_VENDA_A_PRAZO = "PDV_VENDA_A_PRAZO"
    VENDA_CANCELAR = "VENDA_CANCELAR"
    VENDA_DEVOLVER = "VENDA_DEVOLVER"

    # Caixa
    CAIXA_ABRIR = "CAIXA_ABRIR"
    CAIXA_FECHAR = "CAIXA_FECHAR"
    CAIXA_SANGRIA = "CAIXA_SANGRIA"
    CAIXA_SUPRIMENTO = "CAIXA_SUPRIMENTO"

    # Cadastros
    CADASTRO_PRODUTO = "CADASTRO_PRODUTO"
    CADASTRO_CLIENTE = "CADASTRO_CLIENTE"
    LISTA_GERENCIAR = "LISTA_GERENCIAR"

    # Estoque
    ESTOQUE_AJUSTAR = "ESTOQUE_AJUSTAR"
    ESTOQUE_ENTRADA = "ESTOQUE_ENTRADA"

    # Financeiro / relatórios
    TITULO_RECEBER = "TITULO_RECEBER"
    RELATORIO_VER = "RELATORIO_VER"
    RELATORIO_CONTABIL = "RELATORIO_CONTABIL"
    FECHAMENTO_GERAR = "FECHAMENTO_GERAR"
    EXPORTAR_DADOS = "EXPORTAR_DADOS"

    # Administração
    AUDITORIA_VER = "AUDITORIA_VER"
    ADMIN_ACESSAR = "ADMIN_ACESSAR"
    USUARIO_GERENCIAR = "USUARIO_GERENCIAR"
    PERMISSAO_GERENCIAR = "PERMISSAO_GERENCIAR"
    MARCA_GERENCIAR = "MARCA_GERENCIAR"
    TEMA_GERENCIAR = "TEMA_GERENCIAR"
    PARAMETRO_ALTERAR = "PARAMETRO_ALTERAR"
    BACKUP_EXECUTAR = "BACKUP_EXECUTAR"
    BACKUP_RESTAURAR = "BACKUP_RESTAURAR"
    MANUTENCAO_EXECUTAR = "MANUTENCAO_EXECUTAR"

    @property
    def categoria(self) -> CategoriaAcao:
        return {
            Acao.PDV_VENDER: CategoriaAcao.VENDAS,
            Acao.PDV_DESCONTO_ITEM: CategoriaAcao.VENDAS,
            Acao.PDV_DESCONTO_EXCEPCIONAL: CategoriaAcao.VENDAS,
            Acao.PDV_VENDA_ESTOQUE_NEGATIVO: CategoriaAcao.VENDAS,
            Acao.PDV_VENDA_A_PRAZO: CategoriaAcao.VENDAS,
            Acao.VENDA_CANCELAR: CategoriaAcao.VENDAS,
            Acao.VENDA_DEVOLVER: CategoriaAcao.VENDAS,
            Acao.CAIXA_ABRIR: CategoriaAcao.CAIXA,
            Acao.CAIXA_FECHAR: CategoriaAcao.CAIXA,
            Acao.CAIXA_SANGRIA: CategoriaAcao.CAIXA,
            Acao.CAIXA_SUPRIMENTO: CategoriaAcao.CAIXA,
            Acao.CADASTRO_PRODUTO: CategoriaAcao.CADASTROS,
            Acao.CADASTRO_CLIENTE: CategoriaAcao.CADASTROS,
            Acao.LISTA_GERENCIAR: CategoriaAcao.CADASTROS,
            Acao.ESTOQUE_AJUSTAR: CategoriaAcao.ESTOQUE,
            Acao.ESTOQUE_ENTRADA: CategoriaAcao.ESTOQUE,
            Acao.TITULO_RECEBER: CategoriaAcao.FINANCEIRO,
            Acao.RELATORIO_VER: CategoriaAcao.FINANCEIRO,
            Acao.RELATORIO_CONTABIL: CategoriaAcao.FINANCEIRO,
            Acao.FECHAMENTO_GERAR: CategoriaAcao.FINANCEIRO,
            Acao.EXPORTAR_DADOS: CategoriaAcao.FINANCEIRO,
            Acao.AUDITORIA_VER: CategoriaAcao.ADMINISTRACAO,
            Acao.ADMIN_ACESSAR: CategoriaAcao.ADMINISTRACAO,
            Acao.USUARIO_GERENCIAR: CategoriaAcao.ADMINISTRACAO,
            Acao.PERMISSAO_GERENCIAR: CategoriaAcao.ADMINISTRACAO,
            Acao.MARCA_GERENCIAR: CategoriaAcao.ADMINISTRACAO,
            Acao.TEMA_GERENCIAR: CategoriaAcao.ADMINISTRACAO,
            Acao.PARAMETRO_ALTERAR: CategoriaAcao.ADMINISTRACAO,
            Acao.BACKUP_EXECUTAR: CategoriaAcao.ADMINISTRACAO,
            Acao.BACKUP_RESTAURAR: CategoriaAcao.ADMINISTRACAO,
            Acao.MANUTENCAO_EXECUTAR: CategoriaAcao.ADMINISTRACAO,
        }[self]

    @property
    def rotulo(self) -> str:
        return {
            Acao.PDV_VENDER: "Registrar venda",
            Acao.PDV_DESCONTO_ITEM: "Desconto por item",
            Acao.PDV_DESCONTO_EXCEPCIONAL: "Desconto acima do limite",
            Acao.PDV_VENDA_ESTOQUE_NEGATIVO: "Vender com estoque negativo",
            Acao.PDV_VENDA_A_PRAZO: "Venda a prazo (crediário)",
            Acao.VENDA_CANCELAR: "Cancelar venda",
            Acao.VENDA_DEVOLVER: "Devolver venda",
            Acao.CAIXA_ABRIR: "Abrir turno",
            Acao.CAIXA_FECHAR: "Fechar turno",
            Acao.CAIXA_SANGRIA: "Sangria",
            Acao.CAIXA_SUPRIMENTO: "Suprimento",
            Acao.CADASTRO_PRODUTO: "Cadastrar/alterar produto",
            Acao.CADASTRO_CLIENTE: "Cadastrar/alterar cliente",
            Acao.LISTA_GERENCIAR: "Manter listas auxiliares",
            Acao.ESTOQUE_AJUSTAR: "Ajustar estoque",
            Acao.ESTOQUE_ENTRADA: "Registrar entrada de mercadoria",
            Acao.TITULO_RECEBER: "Receber título do crediário",
            Acao.RELATORIO_VER: "Ver relatórios",
            Acao.RELATORIO_CONTABIL: "Ver relatórios contábeis e fechamentos",
            Acao.FECHAMENTO_GERAR: "Gerar fechamento do dia",
            Acao.EXPORTAR_DADOS: "Exportar dados (CSV)",
            Acao.AUDITORIA_VER: "Consultar auditoria",
            Acao.ADMIN_ACESSAR: "Entrar na área administrativa",
            Acao.USUARIO_GERENCIAR: "Criar e gerenciar usuários",
            Acao.PERMISSAO_GERENCIAR: "Definir o que cada perfil pode fazer",
            Acao.MARCA_GERENCIAR: "Alterar dados da loja",
            Acao.TEMA_GERENCIAR: "Alterar cores e tema",
            Acao.PARAMETRO_ALTERAR: "Alterar parâmetros de operação",
            Acao.BACKUP_EXECUTAR: "Gerar cópia de segurança",
            Acao.BACKUP_RESTAURAR: "Restaurar cópia de segurança",
            Acao.MANUTENCAO_EXECUTAR: "Manutenção do banco",
        }[self]

    def __str__(self) -> str:  # pragma: no cover - conveniência de exibição
        return self.rotulo


#: Permissões de fábrica. O Admin Master pode ajustar tudo, exceto a própria
#: linha — que é fixa em "acesso integral" pelo código.
PERMISSOES_PADRAO: dict[Perfil, frozenset[Acao]] = {
    Perfil.ATENDENTE: frozenset(
        {
            Acao.PDV_VENDER,
            Acao.PDV_DESCONTO_ITEM,
            Acao.CAIXA_ABRIR,
            Acao.CAIXA_FECHAR,
            Acao.CAIXA_SUPRIMENTO,
            Acao.TITULO_RECEBER,
            Acao.RELATORIO_VER,
        }
    ),
    Perfil.GERENTE: frozenset(
        {
            Acao.PDV_VENDER,
            Acao.PDV_DESCONTO_ITEM,
            Acao.PDV_DESCONTO_EXCEPCIONAL,
            Acao.PDV_VENDA_ESTOQUE_NEGATIVO,
            Acao.PDV_VENDA_A_PRAZO,
            Acao.VENDA_CANCELAR,
            Acao.VENDA_DEVOLVER,
            Acao.CAIXA_ABRIR,
            Acao.CAIXA_FECHAR,
            Acao.CAIXA_SANGRIA,
            Acao.CAIXA_SUPRIMENTO,
            Acao.CADASTRO_PRODUTO,
            Acao.CADASTRO_CLIENTE,
            Acao.LISTA_GERENCIAR,
            Acao.ESTOQUE_AJUSTAR,
            Acao.ESTOQUE_ENTRADA,
            Acao.TITULO_RECEBER,
            Acao.RELATORIO_VER,
            Acao.RELATORIO_CONTABIL,
            Acao.FECHAMENTO_GERAR,
            Acao.EXPORTAR_DADOS,
            Acao.AUDITORIA_VER,
            Acao.BACKUP_EXECUTAR,
        }
    ),
    # Contabilidade: enxerga dinheiro e documento, não opera caixa.
    Perfil.CONTABILIDADE: frozenset(
        {
            Acao.RELATORIO_VER,
            Acao.RELATORIO_CONTABIL,
            Acao.FECHAMENTO_GERAR,
            Acao.EXPORTAR_DADOS,
            Acao.AUDITORIA_VER,
        }
    ),
    Perfil.ADMIN: frozenset(
        set(Acao)
        - {
            Acao.PERMISSAO_GERENCIAR,  # só o master define a matriz
            Acao.BACKUP_RESTAURAR,  # restauração é decisão do proprietário
        }
    ),
    Perfil.ADMIN_MASTER: frozenset(Acao),
}

#: Ações que jamais podem ser concedidas pelo próprio perfil que as usa.
ACOES_SOMENTE_MASTER: frozenset[Acao] = frozenset(
    {Acao.PERMISSAO_GERENCIAR, Acao.BACKUP_RESTAURAR}
)


@dataclass(frozen=True, slots=True)
class Usuario:
    login: str
    nome: str
    perfil: Perfil
    senha_hash: str = field(repr=False)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ativo: bool = True
    tentativas_falhas: int = 0
    bloqueado_ate: datetime | None = None
    #: Concessões efetivas vindas do banco (o repositório preenche ao carregar).
    #: ``None`` significa "use a matriz padrão do perfil".
    permissoes_concedidas: frozenset[Acao] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.login.strip():
            raise ErroValidacao("Login é obrigatório.")
        if not self.nome.strip():
            raise ErroValidacao("Nome do usuário é obrigatório.")
        if not self.senha_hash:
            raise ErroValidacao("Usuário exige hash de senha; senha em texto é proibida.")

    @property
    def eh_master(self) -> bool:
        return self.perfil.eh_master

    @property
    def permissoes(self) -> frozenset[Acao]:
        if self.eh_master:
            return frozenset(Acao)
        if self.permissoes_concedidas is not None:
            return self.permissoes_concedidas
        return PERMISSOES_PADRAO[self.perfil]

    def pode(self, acao: Acao) -> bool:
        return self.ativo and acao in self.permissoes

    def exigir(self, acao: Acao) -> None:
        if not self.pode(acao):
            raise AutorizacaoNegada(
                f"O perfil {self.perfil.rotulo} não tem permissão para {acao.value}.",
                detalhe={"acao": acao.value, "perfil": self.perfil.value},
            )

    def pode_gerenciar(self, outro: Usuario) -> bool:
        """Só gerencia quem está estritamente abaixo; nunca a si mesmo."""
        if self.id == outro.id:
            return False
        if not self.pode(Acao.USUARIO_GERENCIAR):
            return False
        return self.perfil.nivel > outro.perfil.nivel

    def pode_receber_perfil(self, perfil: Perfil) -> bool:
        """Não se cria nem se promove alguém ao próprio nível ou acima.

        Exceção única: o Admin Master pode criar outro Admin (nível 70), mas
        nunca um segundo master — a instalação tem um proprietário por vez.
        """
        if perfil.eh_master:
            return False
        if self.eh_master:
            return True
        return perfil.nivel < self.perfil.nivel

    def esta_bloqueado(self, agora: datetime) -> bool:
        return self.bloqueado_ate is not None and self.bloqueado_ate > agora


def exigir_autorizacao(
    solicitante: Usuario,
    acao: Acao,
    autorizador: Usuario | None,
) -> None:
    """Regra de dupla checagem para ações excepcionais.

    Ou o próprio usuário tem a permissão, ou um segundo usuário autenticado a
    possui. O autorizador nunca pode ser o mesmo solicitante — e ambos precisam
    ser usuários ativos.
    """
    if solicitante.pode(acao):
        return
    if autorizador is None:
        raise AutorizacaoNegada(
            f"Ação {acao.value} exige autorização de gerente ou administrador.",
            detalhe={"acao": acao.value},
        )
    if autorizador.id == solicitante.id:
        raise AutorizacaoNegada("O autorizador deve ser um usuário diferente do solicitante.")
    autorizador.exigir(acao)


def acoes_por_categoria() -> dict[CategoriaAcao, list[Acao]]:
    """Agrupamento estável (ordem de declaração) para a matriz de permissões."""
    agrupado: dict[CategoriaAcao, list[Acao]] = {c: [] for c in CategoriaAcao}
    for acao in Acao:
        agrupado[acao.categoria].append(acao)
    return agrupado
