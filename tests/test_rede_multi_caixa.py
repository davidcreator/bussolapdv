"""Rede multi-caixa: TLS gerado pelo programa, terminal por requisição e concorrência.

Estes testes sobem o servidor **de verdade** (socket, TLS, threads) contra uma base
em arquivo e conversam por HTTPS. O que se prova, em ordem de risco:

1. o certificado autoassinado que o programa gera é aceito pelo próprio Python
   como CA do cliente — se o DER estiver torto, nada mais funciona;
2. host de rede sem TLS é recusado na linha de comando (não vira HTTP aberto por
   descuido);
3. `X-Bussola-Terminal` chega na venda e no turno — é o que responde "qual caixa
   fez isso" quando a base é uma só;
4. o log de acesso registra cada requisição em JSONL;
5. **dois terminais vendendo ao mesmo tempo** com estoque disputado: uma venda a
   mais do que existe tem que falhar, e não gerar estoque negativo silencioso;
6. as rotas de escrita novas (venda, turno, recebimento, entrada) funcionam.
"""

from __future__ import annotations

import json
import ssl
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bussola_pdv.infra.api import ConfiguracaoAPI, ServidorAPI
from bussola_pdv.infra.rede.certificado import criar_certificado

# ruff: noqa: S310 — as URLs são http(s)://127.0.0.1 montadas no próprio teste
pytestmark = pytest.mark.integracao

TOKEN = "token-de-teste-com-16+"
SENHA = "senha-de-teste"


@pytest.fixture(scope="module")
def certificado(tmp_path_factory):
    """Gerar 2048 bits em Python puro custa ~1 s: uma vez por módulo."""
    return criar_certificado(
        tmp_path_factory.mktemp("tls"), nome="Bussola Teste", bits=2048
    )


@pytest.fixture
def servidor(cenario, certificado, tmp_path):
    log = tmp_path / "acesso.jsonl"
    servidor = ServidorAPI(
        cenario.ctx,
        ConfiguracaoAPI(
            token=TOKEN,
            host="127.0.0.1",
            porta=0,
            tls=certificado,
            terminal="CAIXA-01",
            log_acesso=str(log),
        ),
    ).iniciar()
    yield servidor, log
    servidor.parar()


def _cliente(certificado) -> ssl.SSLContext:
    contexto = ssl.create_default_context(cafile=str(certificado.certificado))
    return contexto


def _pedir(servidor, metodo, rota, corpo=None, *, terminal="", cliente=None, token=TOKEN):
    url = servidor.endereco.replace("/v1", "") + rota
    dados = None if corpo is None else json.dumps(corpo).encode()
    requisicao = urllib.request.Request(url, data=dados, method=metodo)
    requisicao.add_header("Authorization", f"Bearer {token}")
    if dados is not None:
        requisicao.add_header("Content-Type", "application/json")
    if terminal:
        requisicao.add_header("X-Bussola-Terminal", terminal)
    try:
        with urllib.request.urlopen(requisicao, context=cliente, timeout=20) as resposta:
            return resposta.status, json.loads(resposta.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


class TestCertificado:
    def test_programa_gera_certificado_que_o_python_aceita(self, certificado, servidor):
        servidor_api, _ = servidor
        status, corpo = _pedir(
            servidor_api, "GET", "/v1/saude", cliente=_cliente(certificado)
        )
        assert status == 200
        assert corpo["ok"] is True

    def test_sem_confiar_no_certificado_a_conexao_falha(self, servidor):
        """É o ponto do TLS: sem a impressão digital, o terminal não conversa."""
        servidor_api, _ = servidor
        with pytest.raises(urllib.error.URLError):
            _pedir(servidor_api, "GET", "/v1/saude", cliente=ssl.create_default_context())

    def test_impressao_digital_aparece_para_conferencia(self, certificado, servidor):
        servidor_api, _ = servidor
        digital = servidor_api.digital_do_certificado
        assert digital == certificado.digital
        assert digital.count(":") == 31  # SHA-256: 32 bytes em pares hexadecimais

    def test_certificado_e_reaproveitado(self, certificado, tmp_path):
        from bussola_pdv.infra.rede.certificado import obter_ou_criar

        pasta = certificado.certificado.parent
        mesmo = obter_ou_criar(pasta)
        assert mesmo.digital == certificado.digital  # não gera outro a cada subida


class TestTerminalELog:
    def test_terminal_da_requisicao_chega_na_venda(self, cenario, servidor, certificado):
        servidor_api, _ = servidor
        status, corpo = _pedir(
            servidor_api,
            "POST",
            "/v1/vendas",
            {
                "caixa_id": cenario.caixa_id,
                "itens": [{"codigo": cenario.produto_a.codigo, "quantidade": "1"}],
                "pagamentos": [{"forma": "DINHEIRO", "valor_centavos": cenario.produto_a.preco}],
                "operador": {"login": "operador", "senha": SENHA},
            },
            terminal="BALCAO-2",
            cliente=_cliente(certificado),
        )
        assert status == 200, corpo
        assert corpo["terminal"] == "BALCAO-2"
        linha = cenario.ctx.conexao.execute(
            "SELECT terminal_id FROM vendas WHERE id = ?", (corpo["venda_id"],)
        ).fetchone()
        assert linha["terminal_id"] == "BALCAO-2"

    def test_terminal_padrao_quando_o_cabecalho_nao_vem(self, cenario, servidor, certificado):
        servidor_api, _ = servidor
        status, corpo = _pedir(
            servidor_api,
            "POST",
            "/v1/vendas",
            {
                "caixa_id": cenario.caixa_id,
                "itens": [{"codigo": cenario.produto_b.codigo, "quantidade": "1"}],
                "pagamentos": [{"forma": "DINHEIRO", "valor_centavos": cenario.produto_b.preco}],
                "operador": {"login": "operador", "senha": SENHA},
            },
            cliente=_cliente(certificado),
        )
        assert status == 200, corpo
        assert corpo["terminal"] == "CAIXA-01"

    def test_log_de_acesso_registra_cada_requisicao(self, servidor, certificado):
        servidor_api, log = servidor
        _pedir(servidor_api, "GET", "/v1/saude", cliente=_cliente(certificado), terminal="CX-9")
        _pedir(servidor_api, "GET", "/v1/produtos", token="errado", cliente=_cliente(certificado))

        linhas = [json.loads(linha) for linha in log.read_text().splitlines()]
        assert [item["status"] for item in linhas] == [200, 401]
        assert linhas[0]["terminal"] == "CX-9"
        assert linhas[0]["rota"] == "/v1/saude"
        assert linhas[1]["status"] == 401
        assert all("ms" in item for item in linhas)


class TestRotasDeEscrita:
    def test_turno_aberto_e_fechado_pela_api(self, cenario, servidor, certificado):
        servidor_api, _ = servidor
        cliente = _cliente(certificado)
        # o cenário já tem um turno aberto: fechar antes de abrir outro
        _, turnos = _pedir(servidor_api, "GET", "/v1/turnos", cliente=cliente)
        turno_id = turnos["itens"][0]["turno_id"]
        status, corpo = _pedir(
            servidor_api,
            "POST",
            f"/v1/turnos/{turno_id}/fechar",
            {
                "operador": {"login": "gerente", "senha": SENHA},
                "contagens": [{"denominacao": 10000, "quantidade": 1}],
                "motivo_diferenca": "",
            },
            cliente=cliente,
        )
        assert status == 200, corpo
        assert corpo["conferencia"]["classificacao"] == "ZERO"  # diferença zero

        status, corpo = _pedir(
            servidor_api,
            "POST",
            "/v1/turnos",
            {
                "caixa": "Caixa Teste",
                "fundo_centavos": 5000,
                "operador": {"login": "gerente", "senha": SENHA},
            },
            terminal="BALCAO-2",
            cliente=cliente,
        )
        assert status == 200, corpo
        assert corpo["terminal"] == "BALCAO-2"
        assert corpo["esperado_centavos"] == 5000

    def test_entrada_de_estoque_pela_api(self, cenario, servidor, certificado):
        servidor_api, _ = servidor
        antes = cenario.ctx.produtos.saldos()[cenario.produto_a.id]
        status, corpo = _pedir(
            servidor_api,
            "POST",
            "/v1/entradas",
            {
                "fornecedor": "Fornecedor Teste",
                "documento": "NF-1",
                "itens": [
                    {
                        "codigo": cenario.produto_a.codigo,
                        "quantidade": "3",
                        "custo_unitario_centavos": 1000,
                    }
                ],
                "operador": {"login": "gerente", "senha": SENHA},
            },
            cliente=_cliente(certificado),
        )
        assert status == 200, corpo
        depois = cenario.ctx.produtos.saldos()[cenario.produto_a.id]
        assert depois == antes + 3000

    def test_recebimento_com_encargo_pela_api(self, cenario, servidor, certificado):
        from datetime import date, timedelta

        from bussola_pdv.aplicacao.parametros import ServicoParametros
        from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
        from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_a_prazo
        from bussola_pdv.dominio.venda import Carrinho

        carrinho = Carrinho()
        carrinho.adicionar(cenario.produto_a, "1")
        total = carrinho.totais().total
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
                cliente_id=cenario.cliente.id,
                parcelas_crediario=1,
            )
        )
        titulo = next(t for t in cenario.ctx.crediario.listar() if int(t["saldo_centavos"]) > 0)
        atraso = (date.fromisoformat(cenario.ctx.relogio.data_negocio()) - timedelta(days=6))
        cenario.ctx.conexao.execute(
            "UPDATE titulos SET vencimento = ? WHERE id = ?",
            (atraso.isoformat(), titulo["id"]),
        )
        ServicoParametros(cenario.ctx).definir(cenario.admin, "encargos.cobrar", "1")

        servidor_api, _ = servidor
        status, corpo = _pedir(
            servidor_api,
            "POST",
            f"/v1/crediario/{titulo['id']}/receber",
            {
                "valor_centavos": int(titulo["saldo_centavos"]),
                "forma": "DINHEIRO",
                "caixa_id": cenario.caixa_id,
                "operador": {"login": "gerente", "senha": SENHA},
            },
            cliente=_cliente(certificado),
        )
        assert status == 200, corpo
        assert corpo["encargo_centavos"] > 0
        assert corpo["dias_atraso"] == 6
        assert corpo["saldo_restante_centavos"] == 0

    def test_venda_sem_pagamento_e_400(self, cenario, servidor, certificado):
        servidor_api, _ = servidor
        status, corpo = _pedir(
            servidor_api,
            "POST",
            "/v1/vendas",
            {
                "caixa_id": cenario.caixa_id,
                "itens": [{"codigo": cenario.produto_a.codigo, "quantidade": "1"}],
                "pagamentos": [],
                "operador": {"login": "operador", "senha": SENHA},
            },
            cliente=_cliente(certificado),
        )
        assert status == 400
        assert "pagamentos" in corpo["erro"]


class TestConcorrencia:
    def test_dois_terminais_disputando_o_ultimo_item(self, cenario, servidor, certificado):
        """Estoque de 1 unidade, dois caixas vendendo ao mesmo tempo.

        O resultado aceitável é: **uma** venda concluída e a outra recusada com
        mensagem — nunca duas vendas e estoque −1 aparecendo depois no fechamento.
        """
        from bussola_pdv.dominio.dinheiro import Quantidade

        # deixa exatamente 1 unidade de produto_a
        saldo = cenario.ctx.produtos.saldos()[cenario.produto_a.id]
        cenario.ctx.estoque.inserir_movimento(
            produto_id=cenario.produto_a.id,
            tipo=__import__(
                "bussola_pdv.dominio.estoque", fromlist=["TipoMovimentoEstoque"]
            ).TipoMovimentoEstoque.AJUSTE,
            quantidade_milesimos_assinada=1000 - saldo,
            criado_em=cenario.ctx.agora(),
            motivo="teste de concorrência",
        )
        assert cenario.ctx.produtos.saldos()[cenario.produto_a.id] == Quantidade(1000).milesimos

        servidor_api, _ = servidor
        cliente = _cliente(certificado)
        barreira = threading.Barrier(2)  # os dois disparam no mesmo instante

        def vender(terminal: str) -> tuple[int, dict]:
            barreira.wait(timeout=10)  # os dois disparam juntos
            return _pedir(
                servidor_api,
                "POST",
                "/v1/vendas",
                {
                    "caixa_id": cenario.caixa_id,
                    "itens": [{"codigo": cenario.produto_a.codigo, "quantidade": "1"}],
                    "pagamentos": [
                        {"forma": "DINHEIRO", "valor_centavos": cenario.produto_a.preco}
                    ],
                    "operador": {"login": "operador", "senha": SENHA},
                },
                terminal=terminal,
                cliente=cliente,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = [
                futuro.result() for futuro in [executor.submit(vender, "CAIXA-01"),
                                               executor.submit(vender, "BALCAO-2")]
            ]

        aceitos = [corpo for status, corpo in resultados if status == 200]
        recusados = [corpo for status, corpo in resultados if status != 200]
        assert len(aceitos) == 1, resultados
        assert len(recusados) == 1, resultados
        # estoque termina em zero, nunca negativo
        assert cenario.ctx.produtos.saldos()[cenario.produto_a.id] == 0

    def test_requisicoes_paralelas_nao_corrompem_a_base(self, cenario, servidor, certificado):
        """Cinco leituras simultâneas em threads diferentes: conexão é por thread."""
        servidor_api, _ = servidor
        cliente = _cliente(certificado)

        def ler(_: int) -> int:
            status, corpo = _pedir(servidor_api, "GET", "/v1/produtos", cliente=cliente)
            assert status == 200
            return int(corpo["total"])

        with ThreadPoolExecutor(max_workers=5) as executor:
            totais = list(executor.map(ler, range(10)))
        assert len(set(totais)) == 1


def test_host_de_rede_sem_tls_e_recusado_pela_cli(monkeypatch, tmp_path):
    """Erro de configuração precisa estourar na subida, não virar HTTP aberto."""
    from bussola_pdv import cli
    from bussola_pdv.dominio.erros import ErroValidacao

    classe = type("Args", (), {})
    args = classe()
    args.banco = str(tmp_path / "x.db")
    args.token = TOKEN
    args.host = "0.0.0.0"  # noqa: S104 - é justamente o caso que deve ser recusado
    args.porta = 0
    args.tls = False
    args.tls_pasta = None
    args.terminal = "CAIXA-01"
    args.log_acesso = str(tmp_path / "log.jsonl")
    (tmp_path / "x.db").write_bytes(b"")
    with pytest.raises(ErroValidacao, match="TLS"):
        cli.cmd_api(args)


def test_certificado_recusa_chave_ausente(tmp_path):
    from bussola_pdv.infra.rede.certificado import ErroCertificado, ler_certificado

    with pytest.raises(ErroCertificado):
        ler_certificado(tmp_path / "nao-existe.crt")


def test_texto_do_certificado_e_pem_valido(certificado: Path | object) -> None:
    caminho = Path(certificado.certificado)
    texto = caminho.read_text()
    assert texto.startswith("-----BEGIN CERTIFICATE-----")
    assert texto.strip().endswith("-----END CERTIFICATE-----")
