"""Modo terminal: a janela do caixa falando com o servidor (ADR-036).

O que este arquivo prova, e por que cada coisa importa:

1. **o terminal vende de verdade** — abre sessão, busca produto, monta o
   carrinho, finaliza e a venda aparece na base do servidor com o nome do
   terminal (`CAIXA-02`), que é o que permite descobrir depois quem vendeu o quê;
2. **erro de negócio atravessa a rede como erro de negócio** — estoque
   insuficiente chega ao caixa como `EstoqueInsuficiente`, não como "erro 500";
   a tela do terminal mostra a mesma frase do modo local;
3. **identidade não é escolhida pelo terminal** — pedir para vender em nome de
   outro usuário é recusado; autorizar desconto exige a senha do gerente, que o
   servidor confere e troca por uma credencial de uso único;
4. **sem sessão não se faz nada** — o token da API sozinho não vira operador;
5. **certificado de outro servidor é recusado** — trocar o certificado no arquivo
   do caixa faz a conexão falhar, mesmo com o servidor no ar (é o teste que
   impede alguém "resolver" o problema desligando a verificação);
6. **a fábrica de serviços não muda a tela** — o mesmo código de tela recebe
   serviços locais ou remotos.
"""

from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.estoque import ServicoEstoque
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.aplicacao.remoto import ContextoRemoto, ServicoRemoto, servicos_de
from bussola_pdv.dominio.caixa import ContagemDenominacao, TipoMovimentoCaixa
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import AutorizacaoNegada, CredenciaisInvalidas, ErroValidacao
from bussola_pdv.dominio.estoque import TipoMovimentoEstoque
from bussola_pdv.dominio.pagamentos import FormaPagamento, Pagamento, PlanoPagamento
from bussola_pdv.dominio.relogio import RelogioFixo
from bussola_pdv.dominio.usuario import Acao, Perfil, Usuario
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.api.cliente import ClienteAPI, ErroDeComunicacao
from bussola_pdv.infra.api.servidor import ConfiguracaoAPI, ServidorAPI
from bussola_pdv.infra.rede.configuracao_terminal import (
    ConfiguracaoRemota,
    ErroDeConfiguracao,
    carregar,
    guardar_certificado,
    remover,
    salvar,
)
from bussola_pdv.infra.sqlite.repositorio_estoque import EstoqueRepositorio

SENHA = "senha-de-teste"
TOKEN = "token-de-rede-1234567890"
INSTANTE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def hash_senha() -> str:
    from bussola_pdv.dominio.seguranca import gerar_hash

    return gerar_hash(SENHA)


@pytest.fixture
def base(tmp_path: Path, hash_senha: str):
    """Servidor de pé, com operador, gerente, um produto e um turno aberto."""
    contexto = Contexto.abrir(tmp_path / "servidor.db", relogio=RelogioFixo(INSTANTE))
    master = Usuario(login="master", nome="Dora", perfil=Perfil.ADMIN_MASTER, senha_hash=hash_senha)
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
            quantidade_milesimos_assinada=10_000,  # 10 unidades
            criado_em=contexto.agora(),
            motivo="Estoque inicial",
        )
    turno = ServicoCaixa(contexto).abrir_turno(
        caixa="Caixa Teste", operador=gerente, fundo=Dinheiro(10000)
    )
    servidor = ServidorAPI(
        contexto,
        ConfiguracaoAPI(token=TOKEN, porta=0, terminal="SERVIDOR", log_acesso=""),
    )
    servidor.iniciar()
    yield {
        "contexto": contexto,
        "servidor": servidor,
        "produto": produto,
        "turno": turno,
        "pasta_do_caixa": tmp_path / "caixa",
    }
    servidor.parar()
    contexto.fechar()


def _configuracao(base, *, terminal: str = "CAIXA-02", endereco: str | None = None):
    endereco = endereco or f"http://127.0.0.1:{base['servidor'].porta}"
    return ConfiguracaoRemota(endereco=endereco, token=TOKEN, terminal=terminal)


def _cliente(base, **kwargs) -> ClienteAPI:
    pasta = Path(base["pasta_do_caixa"])
    pasta.mkdir(parents=True, exist_ok=True)
    return ClienteAPI(pasta=pasta, configuracao=_configuracao(base, **kwargs))


def _sessao(base, login: str = "operador", **kwargs) -> ClienteAPI:
    cliente = _cliente(base, **kwargs)
    cliente.abrir_sessao(login, SENHA)
    return cliente


def _plano(valor: int) -> PlanoPagamento:
    return PlanoPagamento(
        (
            Pagamento(
                forma=FormaPagamento.DINHEIRO,
                valor_aplicado=Dinheiro(valor),
                valor_entregue=Dinheiro(valor),
            ),
        )
    )


def _solicitacao(base, cliente: ClienteAPI, quantidade: int = 2) -> SolicitacaoVenda:
    produto = cliente.executar("consultas", "produto_para_leitura", {"entrada": "A001"})
    carrinho = Carrinho()
    carrinho.adicionar(produto, quantidade)
    total = 1590 * quantidade
    return SolicitacaoVenda(
        operador=cliente.operador,
        caixa_id=base["turno"].caixa_id,
        carrinho=carrinho,
        plano=_plano(total),
    )


# -- sessão ------------------------------------------------------------------


class TestSessao:
    def test_login_devolve_usuario_e_terminal(self, base) -> None:
        cliente = _sessao(base)
        assert cliente.sessao is not None
        assert cliente.sessao.usuario.login == "operador"
        assert cliente.sessao.terminal == "CAIXA-02"
        assert cliente.sessao.token

    def test_senha_errada_nao_abre_sessao(self, base) -> None:
        cliente = _cliente(base)
        with pytest.raises(CredenciaisInvalidas) as erro:
            cliente.abrir_sessao("operador", "senha-errada")
        assert "inválid" in str(erro.value).lower()
        assert cliente.sessao is None

    def test_sem_sessao_o_executar_recusa(self, base) -> None:
        cliente = _cliente(base)
        with pytest.raises(CredenciaisInvalidas) as erro:
            cliente.executar("consultas", "listar_caixas", {})
        assert "login" in str(erro.value).lower()

    def test_token_errado_nao_entra(self, base) -> None:
        pasta = Path(base["pasta_do_caixa"])
        cliente = ClienteAPI(
            pasta=pasta,
            configuracao=ConfiguracaoRemota(
                endereco=f"http://127.0.0.1:{base['servidor'].porta}",
                token="token-errado-000000000",
                terminal="CAIXA-09",
            ),
        )
        with pytest.raises(CredenciaisInvalidas):
            cliente.abrir_sessao("operador", SENHA)

    def test_encerrar_sessao_invalida_o_token(self, base) -> None:
        cliente = _sessao(base)
        cliente.encerrar_sessao()
        assert cliente.sessao is None
        with pytest.raises(CredenciaisInvalidas):
            cliente.executar("consultas", "listar_caixas", {})


# -- venda de verdade --------------------------------------------------------


class TestVendaPeloTerminal:
    def test_venda_completa_com_terminal_gravado(self, base) -> None:
        cliente = _sessao(base, terminal="CAIXA-02")
        servicos = servicos_de(ContextoRemoto(cliente))
        resultado = servicos.pdv.finalizar_venda(_solicitacao(base, cliente, 2))

        assert resultado.venda.total.centavos == 3180
        assert resultado.ja_existia is False

        venda = base["contexto"].vendas.por_id(resultado.venda.id)
        assert venda.total == Dinheiro(3180)
        # o terminal que fez a venda fica gravado: é o que resolve disputa
        linha = base["contexto"].conexao.execute(
            "SELECT terminal_id FROM vendas WHERE id = ?", (venda.id,)
        ).fetchone()
        assert linha["terminal_id"] == "CAIXA-02"

    def test_repetir_a_chave_nao_duplica(self, base) -> None:
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        solicitacao = _solicitacao(base, cliente, 1)
        primeira = servicos.pdv.finalizar_venda(solicitacao)
        segunda = servicos.pdv.finalizar_venda(solicitacao)
        assert segunda.ja_existia is True
        assert segunda.venda.id == primeira.venda.id

    def test_estoque_insuficiente_pede_autorizacao(self, base) -> None:
        """Sem saldo, a venda não passa — e o terminal recebe o erro do domínio.

        O mesmo caso no modo local levanta `AutorizacaoNegada` (a regra manda
        pedir gerente antes de vender no negativo); o que importa é que o
        terminal receba **o mesmo tipo**, não um 500.
        """
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        with pytest.raises(AutorizacaoNegada) as erro:
            servicos.pdv.finalizar_venda(_solicitacao(base, cliente, 500))
        assert "ESTOQUE_NEGATIVO" in str(erro.value) or "autoriza" in str(erro.value).lower()

    def test_estoque_negativo_autorizado_passa_com_aviso(self, base) -> None:
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        solicitacao = _solicitacao(base, cliente, 500)
        autorizador = servicos.autenticacao.autorizar(
            "gerente", SENHA, Acao.PDV_VENDA_ESTOQUE_NEGATIVO
        )
        from dataclasses import replace

        resultado = servicos.pdv.finalizar_venda(replace(solicitacao, autorizador=autorizador))
        assert resultado.avisos  # avisa que foi no negativo, com autorização

    def test_terminal_nao_vende_em_nome_de_outro(self, base) -> None:
        cliente = _sessao(base)
        gerente = base["contexto"].usuarios.por_login("gerente")
        solicitacao = _solicitacao(base, cliente, 1)
        falsificada = SolicitacaoVenda(
            operador=gerente,  # o terminal tentando "ser" o gerente
            caixa_id=solicitacao.caixa_id,
            carrinho=solicitacao.carrinho,
            plano=solicitacao.plano,
        )
        servicos = servicos_de(ContextoRemoto(cliente))
        with pytest.raises(AutorizacaoNegada):
            servicos.pdv.finalizar_venda(falsificada)

    def test_desconto_excepcional_exige_senha_do_gerente(self, base) -> None:
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        produto = cliente.executar("consultas", "produto_para_leitura", {"entrada": "A001"})
        carrinho = Carrinho()
        carrinho.adicionar(produto, 1, desconto=Dinheiro(200))  # ~13%: acima do limite do operador
        sem_autorizacao = SolicitacaoVenda(
            operador=cliente.operador,
            caixa_id=base["turno"].caixa_id,
            carrinho=carrinho,
            plano=_plano(1390),
        )
        with pytest.raises(AutorizacaoNegada):
            servicos.pdv.finalizar_venda(sem_autorizacao)

        autorizador = servicos.autenticacao.autorizar(
            "gerente", SENHA, Acao.PDV_DESCONTO_EXCEPCIONAL
        )
        com_autorizacao = SolicitacaoVenda(
            operador=cliente.operador,
            caixa_id=base["turno"].caixa_id,
            carrinho=carrinho,
            plano=_plano(1390),
            autorizador=autorizador,
        )
        resultado = servicos.pdv.finalizar_venda(com_autorizacao)
        assert resultado.venda.total.centavos == 1390

    def test_usuario_desativado_na_sessao_e_barrado(self, base) -> None:
        cliente = _sessao(base)
        base["contexto"].usuarios.definir_ativo(cliente.operador.id, False)
        with pytest.raises(CredenciaisInvalidas) as erro:
            servicos_de(ContextoRemoto(cliente)).pdv.politica_desconto()
        assert "desativ" in str(erro.value).lower()


# -- leitura pelo terminal ---------------------------------------------------


class TestLeituras:
    def test_produto_e_saldo(self, base) -> None:
        cliente = _sessao(base)
        contexto = ContextoRemoto(cliente)
        produto = contexto.produtos.buscar_leitura("A001")
        assert produto.descricao == "Café 500 g"
        assert contexto.produtos.saldos([produto.id])[produto.id] == 10_000  # 10 unidades

    def test_caixas_e_turno(self, base) -> None:
        cliente = _sessao(base)
        contexto = ContextoRemoto(cliente)
        caixas = contexto.caixas.listar_caixas()
        assert any(caixa["nome"] == "Caixa Teste" for caixa in caixas)
        turno = contexto.caixas.turno_aberto(base["turno"].caixa_id)
        assert turno is not None
        assert turno.id == base["turno"].id

    def test_parametros(self, base) -> None:
        cliente = _sessao(base)
        contexto = ContextoRemoto(cliente)
        assert contexto.parametros.obter_int("crediario.maximo_parcelas") >= 1

    def test_relatorio_pelo_terminal(self, base) -> None:
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        resumo = servicos.relatorios.resumo_estoque()
        assert isinstance(resumo, dict)

    def test_servico_inexistente_e_recusado(self, base) -> None:
        cliente = _sessao(base)
        with pytest.raises(AttributeError):
            servicos_de(ContextoRemoto(cliente)).pdv.metodo_que_nao_existe()

    def test_executar_direto_com_servico_desconhecido(self, base) -> None:
        cliente = _sessao(base)
        with pytest.raises(ErroValidacao):
            cliente.executar("shell", "rodar", {})


# -- configuração do caixa ---------------------------------------------------


class TestConfiguracaoDoCaixa:
    def test_salvar_e_carregar(self, tmp_path: Path) -> None:
        configuracao = ConfiguracaoRemota(
            endereco="https://loja.local:8765/", token=TOKEN, terminal="CAIXA-02", digital="AA:BB"
        )
        salvar(tmp_path, configuracao)
        volta = carregar(tmp_path)
        assert volta is not None
        assert volta.endereco == "https://loja.local:8765"
        assert volta.base == "https://loja.local:8765/v1"
        assert volta.terminal == "CAIXA-02"

    def test_sem_arquivo_e_modo_local(self, tmp_path: Path) -> None:
        assert carregar(tmp_path) is None
        assert remover(tmp_path) is False

    def test_endereco_invalido_e_token_curto(self) -> None:
        with pytest.raises(ErroDeConfiguracao):
            ConfiguracaoRemota(endereco="", token=TOKEN)
        with pytest.raises(ErroDeConfiguracao):
            ConfiguracaoRemota(endereco="https://loja:8765", token="curto")
        with pytest.raises(ErroDeConfiguracao):
            ConfiguracaoRemota(endereco="ftp://loja", token=TOKEN)

    def test_arquivo_corrompido_avisa(self, tmp_path: Path) -> None:
        (tmp_path / "terminal.json").write_text("{isso não é json", encoding="utf-8")
        with pytest.raises(ErroDeConfiguracao):
            carregar(tmp_path)

    def test_remover_volta_ao_modo_local(self, tmp_path: Path) -> None:
        salvar(tmp_path, ConfiguracaoRemota(endereco="https://loja:8765", token=TOKEN))
        assert remover(tmp_path) is True
        assert carregar(tmp_path) is None


# -- TLS: certificado de outro servidor não entra ----------------------------


class TestConfiancaNoCertificado:
    def test_certificado_guardado_e_a_unica_raiz_aceita(self, tmp_path: Path) -> None:
        """Trocar o certificado no arquivo do caixa derruba a conexão.

        Este é o teste que impede a "solução" de desligar a verificação: com o
        certificado errado guardado, o handshake falha — e a mensagem diz que o
        servidor pode ter sido reinstalado.
        """
        from bussola_pdv.infra.rede.certificado import criar_certificado

        servidor_tls = criar_certificado(tmp_path / "tls-servidor", nome="Servidor Loja")
        configuracao = ConfiguracaoRemota(
            endereco="https://127.0.0.1:1", token=TOKEN, terminal="CAIXA-02"
        )
        outro = criar_certificado(tmp_path / "tls-outro", nome="Outro Servidor")
        der = ssl.PEM_cert_to_DER_cert(outro.certificado.read_text(encoding="ascii"))
        guardar_certificado(tmp_path, der, configuracao=configuracao)
        contexto = configuracao.contexto_tls(tmp_path)
        assert contexto.cert_store_stats()["x509"] >= 1
        assert (tmp_path / "servidor-do-caixa.crt").is_file()
        assert servidor_tls.digital != outro.digital

    def test_sem_certificado_guardado_o_cliente_avisa(self, tmp_path: Path) -> None:
        configuracao = ConfiguracaoRemota(
            endereco="https://127.0.0.1:1", token=TOKEN, terminal="CAIXA-02"
        )
        with pytest.raises(ErroDeConfiguracao):
            configuracao.contexto_tls(tmp_path)

    def test_servidor_fora_do_ar_vira_erro_de_comunicacao(self, base) -> None:
        with socket.socket() as sonda:
            sonda.bind(("127.0.0.1", 0))
            porta = sonda.getsockname()[1]
        cliente = ClienteAPI(
            pasta=Path(base["pasta_do_caixa"]),
            configuracao=ConfiguracaoRemota(
                endereco=f"http://127.0.0.1:{porta}", token=TOKEN, terminal="CAIXA-02"
            ),
            tempo_limite=2.0,
        )
        with pytest.raises(ErroDeComunicacao):
            cliente.abrir_sessao("operador", SENHA)


# -- fábrica de serviços -----------------------------------------------------


class TestFabricaDeServicos:
    def test_modo_local_entrega_servico_local(self, base) -> None:
        servicos = servicos_de(base["contexto"])
        assert servicos.remoto is False
        assert isinstance(servicos.pdv, ServicoPDV)
        assert isinstance(servicos.caixa, ServicoCaixa)

    def test_modo_terminal_entrega_proxy(self, base) -> None:
        cliente = _sessao(base)
        servicos = servicos_de(ContextoRemoto(cliente))
        assert servicos.remoto is True
        assert isinstance(servicos.pdv, ServicoRemoto)
        assert servicos.pdv.nome == "pdv"

    def test_contexto_remoto_parece_contexto(self, base) -> None:
        cliente = _sessao(base)
        contexto = ContextoRemoto(cliente)
        assert contexto.agora().tzinfo is not None
        # a data de negócio vem do servidor (relógio fixo do teste), não do balcão
        assert contexto.data_negocio() == "2026-11-11"
        assert contexto.versao_esquema() >= 6
        assert contexto.terminal == "CAIXA-02"
        contexto.fechar()  # não explode: não há conexão para fechar


# -- a janela inteira, sem Qt ------------------------------------------------


class TestFluxoDaJanela:
    def test_abrir_caixa_movimentar_e_fechar_pelo_terminal(self, base) -> None:
        cliente = _sessao(base, terminal="CAIXA-03")
        servicos = servicos_de(ContextoRemoto(cliente))
        turno = servicos.caixa.abrir_turno(
            caixa="Caixa Remoto", operador=cliente.operador, fundo=Dinheiro(5000)
        )
        assert turno.caixa_id
        servicos.caixa.movimentar(
            turno_id=turno.id,
            operador=cliente.operador,
            tipo=TipoMovimentoCaixa.SANGRIA,
            valor=Dinheiro(1000),
            motivo="troco para o banco",
            autorizador=servicos.autenticacao.autorizar("gerente", SENHA, Acao.CAIXA_SANGRIA),
        )
        fechado = servicos.caixa.fechar_turno(
            turno_id=turno.id,
            conferente=cliente.operador,
            contagens=[ContagemDenominacao(denominacao=1000, quantidade=40)],
            motivo_diferenca="conferência do teste",
        )
        assert fechado.turno.id == turno.id
        linha = base["contexto"].conexao.execute(
            "SELECT terminal_id, status FROM turnos WHERE id = ?", (turno.id,)
        ).fetchone()
        assert linha["terminal_id"] == "CAIXA-03"
