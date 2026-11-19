"""API local: rotas, token, credenciais na escrita e o que ela recusa fazer.

Os testes sobem um servidor de verdade em porta efêmera, em 127.0.0.1, e falam
HTTP com ele — porque a API é justamente a parte que "só funciona na minha
cabeça" até alguém tentar uma requisição.
"""

from __future__ import annotations

# S310: as URLs são montadas pelo próprio teste, sempre em 127.0.0.1.
# ruff: noqa: S310
import json
import urllib.error
import urllib.request

import pytest

from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_dinheiro
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.api import ConfiguracaoAPI, ServidorAPI

TOKEN = "token-de-teste-com-32-caracteres!!"


@pytest.fixture
def api(cenario):
    configuracao = ConfiguracaoAPI(token=TOKEN, porta=0)
    servidor = ServidorAPI(cenario.ctx, configuracao).iniciar()
    try:
        yield servidor
    finally:
        servidor.parar()


def _pedir(
    servidor,
    caminho: str,
    *,
    metodo: str = "GET",
    corpo: dict | None = None,
    token: str | None = TOKEN,
):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    requisicao = urllib.request.Request(servidor.endereco + caminho, data=dados, method=metodo)
    if token:
        requisicao.add_header("Authorization", f"Bearer {token}")
    if dados:
        requisicao.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            return resposta.status, json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode())


def _venda(cenario, quantidade: str = "2") -> str:
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    total = carrinho.totais().total
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_dinheiro(total)),
        )
    )
    return resultado.venda.id


class TestRotasDeLeitura:
    def test_saude_responde_sem_credencial(self, api):
        status, corpo = _pedir(api, "/saude")
        assert status == 200
        assert corpo["ok"] is True
        assert corpo["versao_api"] == "v1"
        assert "escrita" in corpo

    def test_sem_token_e_401(self, api):
        status, corpo = _pedir(api, "/saude", token=None)
        assert status == 401
        assert "Token" in corpo["erro"]

    def test_token_errado_e_401(self, api):
        status, _ = _pedir(api, "/produtos", token="outro-token-qualquer-123456")
        assert status == 401

    def test_produtos_traz_saldo_e_preco(self, api):
        status, corpo = _pedir(api, "/produtos?busca=A001")
        assert status == 200
        assert corpo["total"] == 1
        produto = corpo["itens"][0]
        assert produto["codigo"] == "A001"
        assert produto["preco_centavos"] == 1590
        assert isinstance(produto["saldo_milesimos"], int)

    def test_estoque_sai_do_mesmo_relatorio_da_exportacao(self, api):
        status, corpo = _pedir(api, "/estoque")
        assert status == 200
        assert corpo["titulo"] == "Estoque"
        assert corpo["avisos"]  # aviso de "não é documento fiscal" continua

    def test_venda_por_id_mostra_itens_devolviveis(self, api, cenario):
        venda_id = _venda(cenario, "2")
        status, corpo = _pedir(api, f"/vendas/{venda_id}")
        assert status == 200
        assert corpo["status"] == "CONCLUIDA"
        assert corpo["itens_devolviveis"][0]["devolvivel_milesimos"] == 2000

    def test_rota_inexistente_e_404(self, api):
        status, corpo = _pedir(api, "/nao-existe")
        assert status == 404
        assert "Rota não encontrada" in corpo["erro"]


class TestRotasDeEscrita:
    def test_devolucao_sem_credencial_e_401(self, api, cenario):
        venda_id = _venda(cenario, "1")
        status, corpo = _pedir(
            api,
            "/devolucoes",
            metodo="POST",
            corpo={"venda_id": venda_id, "tipo": "TROCA", "destino": "TROCA", "itens": []},
        )
        assert status == 401
        assert "operador.login" in corpo["erro"]

    def test_devolucao_com_credencial_registra(self, api, cenario):
        venda_id = _venda(cenario, "2")
        item = cenario.ctx.vendas.itens(venda_id)[0]
        status, corpo = _pedir(
            api,
            "/devolucoes",
            metodo="POST",
            corpo={
                "venda_id": venda_id,
                "tipo": "ERRO_OPERACIONAL",
                "destino": "TROCA",
                "motivo": "Item trocado no balcão",
                "itens": [{"sequencia": item["sequencia"], "quantidade": "1"}],
                "operador": {"login": "gerente", "senha": "senha-de-teste"},
            },
        )
        assert status == 200, corpo
        assert corpo["ok"] is True
        assert corpo["total_centavos"] == cenario.produto_a.preco

    def test_devolucao_por_id_traz_os_itens(self, api, cenario):
        venda_id = _venda(cenario, "2")
        item = cenario.ctx.vendas.itens(venda_id)[0]
        _, criada = _pedir(
            api,
            "/devolucoes",
            metodo="POST",
            corpo={
                "venda_id": venda_id,
                "tipo": "ERRO_OPERACIONAL",
                "destino": "TROCA",
                "motivo": "tamanho errado",
                "itens": [{"sequencia": item["sequencia"], "quantidade": "1"}],
                "operador": {"login": "gerente", "senha": "senha-de-teste"},
            },
        )
        status, corpo = _pedir(api, f"/devolucoes/{criada['devolucao_id']}")
        assert status == 200, corpo
        assert corpo["tipo"] == "ERRO_OPERACIONAL"
        assert len(corpo["itens"]) == 1
        assert corpo["itens"][0]["quantidade_milesimos"] == 1000
        assert corpo["itens"][0]["total_centavos"] == cenario.produto_a.preco

    def test_devolucao_inexistente_e_404(self, api):
        status, corpo = _pedir(api, "/devolucoes/DEV-NAOEXISTE")
        assert status == 404
        assert "não encontrada" in corpo["erro"]

    def test_tipo_invalido_lista_os_aceitos(self, api, cenario):
        venda_id = _venda(cenario, "1")
        status, corpo = _pedir(
            api,
            "/devolucoes",
            metodo="POST",
            corpo={
                "venda_id": venda_id,
                "tipo": "NAO_EXISTE",
                "destino": "TROCA",
                "itens": [],
                "operador": {"login": "gerente", "senha": "senha-de-teste"},
            },
        )
        assert status == 400
        assert "ARREPENDIMENTO" in corpo["detalhe"]["tipos"]

    def test_cancelamento_pela_api_exige_autorizador(self, api, cenario):
        venda_id = _venda(cenario, "1")
        status, _corpo = _pedir(
            api,
            f"/vendas/{venda_id}/cancelar",
            metodo="POST",
            corpo={
                "motivo": "cliente desistiu",
                "operador": {"login": "gerente", "senha": "senha-de-teste"},
            },
        )
        # sem autorizador no corpo, a autenticação recusa antes de cancelar
        assert status == 401
        assert cenario.ctx.vendas.por_id(venda_id).status.value == "CONCLUIDA"

    def test_servidor_recusa_token_curto(self, cenario):
        from bussola_pdv.infra.api import ErroAPI

        with pytest.raises(ErroAPI, match="16"):
            ServidorAPI(cenario.ctx, ConfiguracaoAPI(token="curto", porta=0))


class TestDesligamento:
    """O que o servidor deixa para trás quando é desligado.

    Estes dois testes existem por causa de um defeito que só apareceu no CI: o
    programa abre conexão só para ler o certificado do servidor ("Verificar
    servidor") e vai embora sem mandar pedido nenhum. A thread do servidor ficava
    presa na leitura, sobrevivia ao `parar()` e, no fim do interpretador, todo o
    processo caía com `_enter_buffered_busy` — o CI ficava vermelho apontando para
    um teste de layout que não tinha culpa nenhuma.
    """

    def _conectar_e_calar(self, servidor) -> tuple[object, str]:
        import socket

        conexao = socket.create_connection(("127.0.0.1", servidor.porta), timeout=5)
        # Conecta e não manda nada: é o que `inspecionar_certificado` faz.
        return conexao, "process_request_thread"

    def _threads_de_conexao(self) -> list[str]:
        import threading

        return [t.name for t in threading.enumerate() if "process_request_thread" in t.name]

    def test_parar_fecha_conexao_que_nao_mandou_pedido(self, cenario) -> None:
        import time

        servidor = ServidorAPI(cenario.ctx, ConfiguracaoAPI(token=TOKEN, porta=0)).iniciar()
        conexao, _ = self._conectar_e_calar(servidor)
        try:
            servidor.parar()
        finally:
            conexao.close()
        for _tentativa in range(50):  # até 2 s: desligar não pode deixar thread viva
            if not self._threads_de_conexao():
                break
            time.sleep(0.04)
        assert self._threads_de_conexao() == []

    def test_cliente_que_desiste_nao_imprime_traceback(self, cenario, capfd) -> None:
        servidor = ServidorAPI(cenario.ctx, ConfiguracaoAPI(token=TOKEN, porta=0)).iniciar()
        conexao, _ = self._conectar_e_calar(servidor)
        conexao.close()  # foi embora sem pedir nada: rotina, não erro
        servidor.parar()
        erro = capfd.readouterr().err
        assert "Traceback" not in erro
        assert "BrokenPipeError" not in erro
        assert "ConnectionResetError" not in erro
