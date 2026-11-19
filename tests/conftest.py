"""Fixtures compartilhadas: banco temporário real, relógio fixo e cenário mínimo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.relogio import RelogioFixo
from bussola_pdv.dominio.seguranca import gerar_hash
from bussola_pdv.dominio.usuario import Perfil, Usuario

SENHA = "senha-de-teste"
_INSTANTE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)  # 09:00 em São Paulo

#: Referência viva da `QApplication` da sessão. Existe porque no PySide6 o objeto
#: Qt é destruído quando a última referência Python morre: cada arquivo de teste
#: tinha a sua fixture local, a aplicação era coletada ao fim do arquivo e o
#: seguinte criava outra — e criar/destruir `QApplication` no mesmo processo é
#: caminho conhecido de segfault (aconteceu no CI, no meio de outro arquivo).
#: Uma aplicação por sessão, segurada aqui, elimina a classe inteira do problema.
_APLICACAO_QT: object | None = None


@pytest.fixture(scope="session", autouse=True)
def aplicacao_qt() -> object | None:
    """Cria (uma vez) a `QApplication` usada pelos testes de interface.

    Autouse e de sessão: assim nenhuma fixture local descarta a aplicação no meio
    da suíte. Se o PySide6 não estiver instalado, devolve `None` — os testes que
    precisam de Qt já se pulam sozinhos com `importorskip`.
    """
    global _APLICACAO_QT
    if _APLICACAO_QT is not None:
        return _APLICACAO_QT
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # sem Qt instalado: nada a fazer, e nada quebra
        return None
    import os

    # Sem vídeo no CI e nos runners: a plataforma offscreen é a única que abre.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    aplicacao = QApplication.instance() or QApplication(["teste"])
    try:
        from bussola_pdv.ui.tema import FOLHA_ESTILO

        aplicacao.setStyleSheet(FOLHA_ESTILO)
    except ImportError:  # pragma: no cover - tema é do próprio pacote
        pass
    _APLICACAO_QT = aplicacao
    return aplicacao


@pytest.fixture(scope="session")
def hash_senha() -> str:
    """Argon2id é caro de propósito: gera uma vez por sessão de testes."""
    return gerar_hash(SENHA)


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo(_INSTANTE)


@pytest.fixture
def ctx(tmp_path, relogio) -> Contexto:
    contexto = Contexto.abrir(tmp_path / "bussola_teste.db", relogio=relogio)
    yield contexto
    contexto.fechar()


@dataclass
class Cenario:
    ctx: Contexto
    master: Usuario
    admin: Usuario
    gerente: Usuario
    contabilidade: Usuario
    operador: Usuario
    caixa_id: str
    turno_id: str
    produto_a: object
    produto_b: object
    cliente: object


def _usuario(login: str, nome: str, perfil: Perfil, hash_senha: str) -> Usuario:
    return Usuario(login=login, nome=nome, perfil=perfil, senha_hash=hash_senha)


@pytest.fixture
def cenario(ctx: Contexto, hash_senha: str) -> Cenario:
    """Cenário mínimo: 2 produtos, 1 cliente, caixa aberto com fundo de R$ 100."""
    master = _usuario("master", "Dora Proprietária", Perfil.ADMIN_MASTER, hash_senha)
    admin = _usuario("admin", "Ana Admin", Perfil.ADMIN, hash_senha)
    gerente = _usuario("gerente", "Bruno Gerente", Perfil.GERENTE, hash_senha)
    contabilidade = _usuario("contador", "Elias Contador", Perfil.CONTABILIDADE, hash_senha)
    operador = _usuario("operador", "Carla Atendente", Perfil.ATENDENTE, hash_senha)
    agora = ctx.agora().isoformat()
    with ctx.em_transacao():
        for usuario in (master, admin, gerente, contabilidade, operador):
            ctx.usuarios.criar(usuario, criado_em=agora, criado_por=master.id)
    # recarrega com as permissões efetivas, como faz a aplicação de verdade
    master = ctx.usuarios.por_id(master.id)
    admin = ctx.usuarios.por_id(admin.id)
    gerente = ctx.usuarios.por_id(gerente.id)
    contabilidade = ctx.usuarios.por_id(contabilidade.id)
    operador = ctx.usuarios.por_id(operador.id)

    from bussola_pdv.aplicacao.estoque import ServicoEstoque

    servico_estoque = ServicoEstoque(ctx)
    produto_a = servico_estoque.criar_produto(
        operador=admin,
        codigo="A001",
        descricao="Café 500 g",
        preco=1590,
        custo=1000,
        categoria="Mercearia",
        estoque_minimo=2000,  # milésimos: 2 unidades
        codigo_barras="7891234567895",
    )
    produto_b = servico_estoque.criar_produto(
        operador=admin,
        codigo="B002",
        descricao="Feijão a granel",
        preco=990,
        custo=600,
        categoria="Mercearia",
        unidade="KG",
        estoque_minimo=2000,
    )

    from bussola_pdv.dominio.estoque import TipoMovimentoEstoque
    from bussola_pdv.infra.sqlite.repositorio_estoque import EstoqueRepositorio

    with ctx.em_transacao():
        estoque = EstoqueRepositorio(ctx.conexao)
        estoque.inserir_movimento(
            produto_id=produto_a.id,
            tipo=TipoMovimentoEstoque.ENTRADA,
            quantidade_milesimos_assinada=10_000,
            criado_em=ctx.agora(),
            motivo="Estoque inicial",
        )
        estoque.inserir_movimento(
            produto_id=produto_b.id,
            tipo=TipoMovimentoEstoque.ENTRADA,
            quantidade_milesimos_assinada=5_000,
            criado_em=ctx.agora(),
            motivo="Estoque inicial",
        )

    from bussola_pdv.dominio.cliente import Cliente

    cliente = Cliente(nome="Cliente Teste", limite_credito=10_000)
    with ctx.em_transacao():
        ctx.clientes.criar(cliente, criado_em=agora)

    caixa = ServicoCaixa(ctx)
    turno = caixa.abrir_turno(caixa="Caixa Teste", operador=gerente, fundo=Dinheiro(10000))

    return Cenario(
        ctx=ctx,
        master=master,
        admin=admin,
        gerente=gerente,
        contabilidade=contabilidade,
        operador=operador,
        caixa_id=turno.caixa_id,
        turno_id=turno.id,
        produto_a=produto_a,
        produto_b=produto_b,
        cliente=cliente,
    )
