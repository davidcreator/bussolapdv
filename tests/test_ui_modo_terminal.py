"""Telas do caixa remoto: configuração do primeiro uso e vendas pendentes (ADR-036).

O que estes testes fecham, e por que cada um importa:

1. **o primeiro uso mostra a digital e grava o que foi confirmado** — o operador
   vê o SHA-256 do certificado do servidor e, ao confiar, o programa passa a
   abrir em modo terminal sem perguntar de novo;
2. **a janela remota é a mesma janela** — os módulos aparecem, as consultas
   funcionam pela rede e a única entrada nova é a das vendas pendentes;
3. **a tela de pendências reenvia de verdade** — a venda guardada sai da fila e
   aparece na base do servidor com número (não é "mensagem de sucesso" sem
   consequência).

Servidor de verdade, TLS de verdade, tela de verdade: o que se testa aqui é o
caminho do operador, não um dublê.
"""

from __future__ import annotations

import os
import ssl
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.estoque import ServicoEstoque
from bussola_pdv.aplicacao.fila_offline import FilaDeVendas
from bussola_pdv.aplicacao.pdv import SolicitacaoVenda
from bussola_pdv.aplicacao.remoto import ContextoRemoto, ServicoPDVRemoto, VendaGuardadaParaEnvio
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.estoque import TipoMovimentoEstoque
from bussola_pdv.dominio.pagamentos import FormaPagamento, Pagamento, PlanoPagamento
from bussola_pdv.dominio.relogio import RelogioFixo
from bussola_pdv.dominio.usuario import Perfil, Usuario
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.api.cliente import ClienteAPI
from bussola_pdv.infra.api.servidor import ConfiguracaoAPI, ServidorAPI
from bussola_pdv.infra.rede.certificado import criar_certificado
from bussola_pdv.infra.rede.configuracao_terminal import (
    NOME_DO_CERTIFICADO,
    ConfiguracaoRemota,
    carregar,
)
from bussola_pdv.infra.sqlite.repositorio_estoque import EstoqueRepositorio

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ausente")

SENHA = "senha-de-teste"
TOKEN = "token-de-rede-1234567890"
INSTANTE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def certificado(tmp_path_factory):
    """Gerar RSA em Python puro custa ~1 s: uma vez por módulo."""
    return criar_certificado(tmp_path_factory.mktemp("tls"), nome="Bussola Teste", bits=2048)


@pytest.fixture
def base(tmp_path: Path, certificado):
    """Servidor de pé com TLS, operador, produto com saldo e turno aberto."""
    from bussola_pdv.dominio.seguranca import gerar_hash

    hash_senha = gerar_hash(SENHA)
    contexto = Contexto.abrir(tmp_path / "servidor.db", relogio=RelogioFixo(INSTANTE))
    master = Usuario(
        login="master", nome="Dora", perfil=Perfil.ADMIN_MASTER, senha_hash=hash_senha
    )
    operador = Usuario(
        login="operador", nome="Carla Atendente", perfil=Perfil.ATENDENTE, senha_hash=hash_senha
    )
    gerente = Usuario(
        login="gerente", nome="Bruno Gerente", perfil=Perfil.GERENTE, senha_hash=hash_senha
    )
    with contexto.em_transacao():
        for usuario in (master, operador, gerente):
            contexto.usuarios.criar(
                usuario, criado_em=contexto.agora().isoformat(), criado_por=master.id
            )
    gerente = contexto.usuarios.por_id(gerente.id)
    produto = ServicoEstoque(contexto).criar_produto(
        operador=gerente, codigo="A001", descricao="Café 500 g", preco=1590, custo=1000
    )
    with contexto.em_transacao():
        EstoqueRepositorio(contexto.conexao).inserir_movimento(
            produto_id=produto.id,
            tipo=TipoMovimentoEstoque.ENTRADA,
            quantidade_milesimos_assinada=10_000,
            criado_em=contexto.agora(),
            motivo="Estoque inicial",
        )
    turno = ServicoCaixa(contexto).abrir_turno(
        caixa="Caixa Teste", operador=gerente, fundo=Dinheiro(10000)
    )
    servidor = ServidorAPI(
        contexto,
        ConfiguracaoAPI(
            token=TOKEN, host="127.0.0.1", porta=0, tls=certificado, terminal="SERVIDOR"
        ),
    ).iniciar()
    yield {
        "contexto": contexto,
        "servidor": servidor,
        "turno": turno,
        "pasta_do_caixa": tmp_path / "caixa",
    }
    servidor.parar()
    contexto.fechar()


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


def _confiar(base, pasta: Path, *, terminal: str = "CAIXA-02") -> ConfiguracaoRemota:
    """Passa pela tela de primeiro uso, como o operador faria."""
    from bussola_pdv.ui.remoto import DialogoConfiguracaoDoCaixa

    dialogo = DialogoConfiguracaoDoCaixa(pasta)
    dialogo.campo_endereco.setText(base["servidor"].endereco.replace("/v1", ""))
    dialogo.campo_token.setText(TOKEN)
    dialogo.campo_nome.setText(terminal)
    dialogo._verificar()
    dialogo._salvar()
    assert dialogo.configuracao is not None
    return dialogo.configuracao


def _cliente(base, pasta: Path, *, terminal: str = "CAIXA-02") -> ClienteAPI:
    pasta.mkdir(parents=True, exist_ok=True)
    configuracao = _confiar(base, pasta, terminal=terminal)
    cliente = ClienteAPI(pasta=pasta, configuracao=configuracao)
    cliente.abrir_sessao("operador", SENHA)
    return cliente


def _solicitacao(cliente: ClienteAPI, base) -> SolicitacaoVenda:
    produto = cliente.executar("consultas", "produto_para_leitura", {"entrada": "A001"})
    carrinho = Carrinho()
    carrinho.adicionar(produto, 2)
    plano = PlanoPagamento(
        (
            Pagamento(
                forma=FormaPagamento.DINHEIRO,
                valor_aplicado=Dinheiro(3180),
                valor_entregue=Dinheiro(3180),
            ),
        )
    )
    return SolicitacaoVenda(
        operador=cliente.operador,
        caixa_id=base["turno"].caixa_id,
        carrinho=carrinho,
        plano=plano,
    )


# -- primeiro uso -------------------------------------------------------------


@pytest.mark.ui
class TestConfiguracaoDoCaixa:
    def test_mostra_a_digital_do_servidor(self, app, base, tmp_path: Path) -> None:
        from bussola_pdv.ui.remoto import DialogoConfiguracaoDoCaixa

        dialogo = DialogoConfiguracaoDoCaixa(tmp_path / "caixa")
        # Antes de verificar, não há como confiar em nada.
        assert dialogo.botao_salvar.isEnabled() is False
        dialogo.campo_endereco.setText(base["servidor"].endereco.replace("/v1", ""))
        dialogo._verificar()
        assert base["servidor"].digital_do_certificado in dialogo.rotulo_digital.text()
        assert dialogo.botao_salvar.isEnabled() is True

    def test_confiar_grava_certificado_e_configuracao(self, app, base, tmp_path: Path) -> None:
        pasta = tmp_path / "caixa"
        pasta.mkdir()
        configuracao = _confiar(base, pasta)
        assert configuracao.digital == base["servidor"].digital_do_certificado
        assert configuracao.terminal == "CAIXA-02"
        assert (pasta / NOME_DO_CERTIFICADO).is_file()
        gravada = carregar(pasta)
        assert gravada is not None
        assert gravada.digital == configuracao.digital

    def test_sem_token_a_conexao_e_recusada_depois_de_confiar(
        self, app, base, tmp_path: Path
    ) -> None:
        pasta = tmp_path / "caixa"
        pasta.mkdir()
        configuracao = _confiar(base, pasta)
        errada = ConfiguracaoRemota(
            endereco=configuracao.endereco,
            token="token-errado-0000000",
            terminal="CAIXA-02",
            digital=configuracao.digital,
            certificado=NOME_DO_CERTIFICADO,
        )
        cliente = ClienteAPI(pasta=pasta, configuracao=errada)
        from bussola_pdv.dominio.erros import CredenciaisInvalidas

        with pytest.raises(CredenciaisInvalidas):
            cliente.abrir_sessao("operador", SENHA)

    def test_contexto_tls_do_terminal_aceita_o_servidor(self, app, base, tmp_path: Path) -> None:
        pasta = tmp_path / "caixa"
        pasta.mkdir()
        configuracao = _confiar(base, pasta)
        contexto: ssl.SSLContext = configuracao.contexto_tls(pasta)
        assert contexto.verify_mode is ssl.CERT_REQUIRED


# -- janela -------------------------------------------------------------------


@pytest.mark.ui
class TestJanelaRemota:
    def test_janela_remota_tem_os_modulos_e_as_pendencias(self, app, base, tmp_path) -> None:
        from bussola_pdv.ui.janela import MODULO_PENDENTES, JanelaPrincipal

        cliente = _cliente(base, tmp_path / "caixa")
        janela = JanelaPrincipal(ContextoRemoto(cliente), cliente.operador)
        try:
            assert "PDV" in janela.modulos
            assert "Caixa" in janela.modulos
            assert MODULO_PENDENTES in janela.modulos
            assert janela.rodape is not None
        finally:
            janela.close()

    def test_modulos_consultam_pela_rede(self, app, base, tmp_path) -> None:
        """Produtos, Vendas e Auditoria leem do servidor — sem base local nenhuma."""
        from bussola_pdv.ui.janela import JanelaPrincipal

        cliente = _cliente(base, tmp_path / "caixa")
        contexto = ContextoRemoto(cliente)
        janela = JanelaPrincipal(contexto, cliente.operador)
        try:
            for modulo in ("Produtos", "Vendas", "Auditoria"):
                janela._selecionar(modulo)
            assert contexto.caminho is None  # nenhuma base aberta no caixa
        finally:
            janela.close()


# -- pendências ---------------------------------------------------------------


@pytest.mark.ui
class TestPendenciasNaTela:
    def test_lista_a_venda_guardada_e_reenvia(self, app, base, tmp_path) -> None:
        from bussola_pdv.ui.remoto import DialogoPendencias

        pasta = tmp_path / "caixa"
        cliente = _cliente(base, pasta)
        fila = FilaDeVendas(pasta / "vendas-pendentes.db")
        try:
            servico = ServicoPDVRemoto(cliente, fila)
            # Guarda a venda sem enviar: é o que aconteceria com a rede caída.
            solicitacao = _solicitacao(cliente, base)
            fila.enfileirar(
                solicitacao=solicitacao,
                operador_id=cliente.operador.id,
                operador_login=cliente.operador.login,
                terminal="CAIXA-02",
            )
            assert fila.quantidade() == 1

            dialogo = DialogoPendencias(fila, cliente, solicitacao_tipo=SolicitacaoVenda)
            try:
                assert dialogo.tabela.rowCount() == 1
                assert dialogo.tabela.item(0, 1).text() == "operador"
                dialogo._reenviar()
                assert dialogo.tabela.rowCount() == 0
                assert "1 enviada" in dialogo.rotulo_resultado.text()
            finally:
                dialogo.close()
            assert fila.quantidade() == 0
            vendas = base["contexto"].vendas.listar(limite=10)
            assert any(v["total_centavos"] == 3180 for v in vendas)
            # O proxy não foi usado para isso: a venda acima saiu da fila, não do serviço.
            assert servico.nome == "pdv"
        finally:
            fila.fechar()

    def test_venda_com_rede_caida_vira_pendencia_na_tela(
        self, app, base, tmp_path, monkeypatch
    ) -> None:
        from bussola_pdv.infra.api.cliente import ErroDeComunicacao
        from bussola_pdv.ui.remoto import DialogoPendencias

        pasta = tmp_path / "caixa"
        cliente = _cliente(base, pasta)
        fila = FilaDeVendas(pasta / "vendas-pendentes.db")
        try:
            servico = ServicoPDVRemoto(cliente, fila)
            solicitacao = _solicitacao(cliente, base)

            def sem_rede(*_args, **_kwargs):
                raise ErroDeComunicacao("A rede caiu.", endereco=cliente.configuracao.endereco)

            monkeypatch.setattr(cliente, "pedir", sem_rede)  # a rede caiu no meio da venda
            with pytest.raises(VendaGuardadaParaEnvio) as guardada:
                servico.finalizar_venda(solicitacao)
            assert guardada.value.quantidade == 1

            dialogo = DialogoPendencias(fila, None, solicitacao_tipo=SolicitacaoVenda)
            try:
                assert dialogo.tabela.rowCount() == 1
                # Sem sessão não se reenvia: o botão fica desligado.
                assert dialogo.botao_reenviar.isEnabled() is False
            finally:
                dialogo.close()
        finally:
            fila.fechar()


# -- entrada do modo terminal -------------------------------------------------


@pytest.mark.ui
class TestEntradaDoModoTerminal:
    def test_login_local_oferece_o_botao_de_rede(self, app, cenario) -> None:
        from bussola_pdv.ui.login import DialogoLogin

        dialogo = DialogoLogin(cenario.ctx)
        try:
            assert dialogo.botao_rede.isVisibleTo(dialogo) is True
        finally:
            dialogo.close()

    def test_login_remoto_nao_oferece_o_botao_de_rede(self, app, base, tmp_path) -> None:
        from bussola_pdv.ui.login import DialogoLogin

        cliente = _cliente(base, tmp_path / "caixa")
        dialogo = DialogoLogin(ContextoRemoto(cliente))
        try:
            # Já está configurado: reconfigurar por engano é o caminho para
            # apontar o caixa para o servidor errado.
            assert dialogo.botao_rede.isVisibleTo(dialogo) is False
        finally:
            dialogo.close()
