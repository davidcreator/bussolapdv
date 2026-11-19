"""API HTTP local: o mesmo serviço de aplicação, agora alcançável por HTTP.

Por que existe: o terminal do balcão é um programa com tela; o *servidor* do
multi-caixa (e qualquer integração futura — totem, coletor, planilha) fala HTTP.
Em vez de uma segunda regra de negócio, esta API **chama os mesmos serviços** da
interface. Nenhum cálculo novo acontece aqui.

Postura de segurança (deliberada, e documentada em docs/API.md):

* escuta em **127.0.0.1** por padrão — abrir para a rede é decisão explícita
  (`--host`), e continua exigindo token;
* token obrigatório em **toda** rota (cabeçalho ``Authorization: Bearer``);
* toda rota que grava exige, além do token, **login e senha** do operador (e do
  autorizador quando a regra pede): o token identifica o aplicativo, não a pessoa;
* nada sai para a internet. Não há telemetria, não há chamada externa.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from ...aplicacao.autenticacao import ServicoAutenticacao
from ...aplicacao.caixa import ServicoCaixa
from ...aplicacao.contexto import Contexto
from ...aplicacao.crediario import ServicoCrediario
from ...aplicacao.devolucao import ItemSolicitado, ServicoDevolucao
from ...aplicacao.estoque import ServicoEstoque
from ...aplicacao.exportacao import ServicoExportacao
from ...aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from ...dominio.caixa import ContagemDenominacao
from ...dominio.devolucao import DestinoDevolucao, TipoDevolucao
from ...dominio.dinheiro import Dinheiro, Quantidade
from ...dominio.erros import ErroBussola, ErroNaoEncontrado, ErroValidacao
from ...dominio.estoque import EntradaMercadoria, ItemEntrada
from ...dominio.pagamentos import (
    FormaPagamento,
    Pagamento,
    PlanoPagamento,
    pagamento_a_prazo,
    pagamento_dinheiro,
    pagamento_eletronico,
)
from ...dominio.usuario import Acao
from ...dominio.venda import Carrinho

VERSAO_API = "v1"


class ErroAPI(Exception):
    def __init__(self, status: HTTPStatus, mensagem: str, detalhe: Any = None) -> None:
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem
        self.detalhe = detalhe


@dataclass(frozen=True, slots=True)
class ConfiguracaoAPI:
    token: str
    host: str = "127.0.0.1"
    porta: int = 8765
    #: Rotas só de leitura não precisam de senha; qualquer escrita precisa.
    exigir_credenciais_na_escrita: bool = True
    #: Certificado do servidor (v0.14.0). Sem ele, HTTP em claro — aceitável só
    #: em 127.0.0.1; para a rede da loja, `bussola api --tls` gera e usa um.
    tls: Any = None
    #: Terminal padrão quando a requisição não manda `X-Bussola-Terminal`.
    terminal: str = "CAIXA-01"
    #: Arquivo JSONL de acessos (um por requisição). `None` = não registra.
    log_acesso: str = ""


@dataclass
class ServicoWeb:
    """Rotas da API. Devolve dicionários prontos para JSON.

    O contexto é **por thread**: conexão SQLite não atravessa thread (e o servidor
    é multi-thread de propósito). A fábrica abre a base de novo para cada thread
    que atende uma requisição — sem estado compartilhado, sem dado corrompido.
    """

    fabrica: Callable[[], Contexto]
    configuracao: ConfiguracaoAPI
    rotas_escrita: tuple[str, ...] = field(default=("POST", "PUT", "PATCH", "DELETE"))
    _local: threading.local = field(default_factory=threading.local, init=False, repr=False)

    #: Terminal da requisição em andamento (o manipulador troca antes de tratar).
    @property
    def terminal(self) -> str:
        return getattr(self._local, "terminal", self.configuracao.terminal)

    @terminal.setter
    def terminal(self, valor: str) -> None:
        self._local.terminal = valor or self.configuracao.terminal

    @property
    def contexto(self) -> Contexto:
        contexto = getattr(self._local, "contexto", None)
        if contexto is None:
            contexto = self.fabrica()
            self._local.contexto = contexto
        contexto.terminal = self.terminal
        return contexto

    # -- roteamento ---------------------------------------------------------
    def tratar(self, metodo: str, caminho: str, consulta: dict[str, list[str]], corpo: dict) -> dict:
        partes = [pedaco for pedaco in urlparse(caminho).path.split("/") if pedaco]
        if not partes or partes[0] != VERSAO_API:
            raise ErroAPI(HTTPStatus.NOT_FOUND, f"Use o prefixo /{VERSAO_API}.")
        recurso = partes[1] if len(partes) > 1 else ""

        if recurso == "saude" and metodo == "GET":
            return self.saude()
        if recurso == "produtos" and metodo == "GET":
            return self.produtos(consulta)
        if recurso == "estoque" and metodo == "GET":
            return self.estoque(consulta)
        if recurso == "crediario":
            if metodo == "GET":
                return self.crediario(consulta)
            if metodo == "POST" and len(partes) == 4 and partes[3] == "receber":
                return self.receber_titulo(partes[2], corpo)
        if recurso == "turnos":
            if metodo == "GET":
                return self.turnos(consulta)
            if metodo == "POST" and len(partes) == 2:
                return self.abrir_turno(corpo)
            if metodo == "POST" and len(partes) == 4 and partes[3] == "fechar":
                return self.fechar_turno(partes[2], corpo)
        if recurso == "entradas" and metodo == "POST":
            return self.lancar_entrada(corpo)
        if recurso == "vendas":
            if metodo == "GET" and len(partes) == 2:
                return self.vendas(consulta)
            if metodo == "POST" and len(partes) == 2:
                return self.finalizar_venda(corpo)
            if metodo == "GET" and len(partes) == 3:
                return self.venda(partes[2])
            if metodo == "POST" and len(partes) == 4 and partes[3] == "cancelar":
                return self.cancelar_venda(partes[2], corpo)
        if recurso == "devolucoes":
            if metodo == "GET" and len(partes) == 2:
                return self.devolucoes(consulta)
            if metodo == "GET" and len(partes) == 3:
                return self.devolucao(partes[2])
            if metodo == "POST":
                return self.registrar_devolucao(corpo)
        if recurso == "relatorios" and metodo == "GET" and len(partes) == 3:
            return self.relatorio(partes[2], consulta)
        raise ErroAPI(HTTPStatus.NOT_FOUND, f"Rota não encontrada: {metodo} {caminho}")

    # -- leitura ------------------------------------------------------------
    def saude(self) -> dict:
        return {
            "ok": True,
            "versao_api": VERSAO_API,
            "esquema": self.contexto.versao_esquema(),
            "data_negocio": self.contexto.data_negocio(),
            "escrita": "exige login e senha do operador",
        }

    def produtos(self, consulta: dict[str, list[str]]) -> dict:
        busca = (consulta.get("busca") or [""])[0]
        limite = int((consulta.get("limite") or ["200"])[0])
        saldos = self.contexto.produtos.saldos()
        produtos = self.contexto.produtos.listar(
            busca=busca, apenas_ativos=False, limite=limite
        )
        return {
            "total": len(produtos),
            "itens": [
                {
                    "id": produto.id,
                    "codigo": produto.codigo,
                    "codigo_barras": produto.codigo_barras,
                    "descricao": produto.descricao,
                    "categoria": produto.categoria,
                    "unidade": produto.unidade.value,
                    "preco_centavos": produto.preco,
                    "custo_centavos": produto.custo,
                    "ativo": produto.ativo,
                    "garantia_dias": produto.garantia_dias,
                    "saldo_milesimos": saldos.get(produto.id, 0),
                }
                for produto in produtos
            ],
        }

    def estoque(self, consulta: dict[str, list[str]]) -> dict:
        busca = (consulta.get("busca") or [""])[0]
        relatorio = ServicoExportacao(self.contexto).relatorio_estoque(busca)
        tabela = relatorio.tabelas[0]
        return {
            "titulo": relatorio.titulo,
            "data_negocio": self.contexto.data_negocio(),
            "colunas": [coluna.titulo for coluna in tabela.colunas],
            "linhas": [list(linha) for linha in tabela.linhas],
            "avisos": list(relatorio.avisos),
        }

    def crediario(self, consulta: dict[str, list[str]]) -> dict:
        cliente_id = (consulta.get("cliente_id") or [""])[0] or None
        incluir_pagos = (consulta.get("incluir_pagos") or ["0"])[0] in {"1", "true", "sim"}
        titulos = self.contexto.crediario.listar(
            cliente_id=cliente_id,
            incluir_pagos=incluir_pagos,
            referencia=self.contexto.data_negocio(),
        )
        return {"total": len(titulos), "itens": titulos}

    def vendas(self, consulta: dict[str, list[str]]) -> dict:
        limite = int((consulta.get("limite") or ["100"])[0])
        vendas = self.contexto.vendas.listar(
            data_inicial=(consulta.get("de") or [""])[0] or None,
            data_final=(consulta.get("ate") or [""])[0] or None,
            limite=limite,
        )
        return {"total": len(vendas), "itens": vendas}

    def venda(self, venda_id: str) -> dict:
        venda = self.contexto.vendas.por_id(venda_id)
        return {
            "id": venda.id,
            "rotulo": venda.rotulo,
            "data_negocio": venda.data_negocio,
            "status": venda.status.value,
            "total_centavos": venda.total.centavos,
            "cliente_id": venda.cliente_id,
            "itens": self.contexto.vendas.itens(venda_id),
            "pagamentos": self.contexto.vendas.pagamentos(venda_id),
            "devolvido_centavos": self.contexto.devolucoes.total_devolvido(venda_id),
            "itens_devolviveis": ServicoDevolucao(self.contexto).itens_devolviveis(venda_id),
        }

    def devolucoes(self, consulta: dict[str, list[str]]) -> dict:
        venda_id = (consulta.get("venda_id") or [""])[0] or None
        limite = int((consulta.get("limite") or ["100"])[0])
        registros = ServicoDevolucao(self.contexto).listar(limite=limite, venda_id=venda_id)
        return {"total": len(registros), "itens": registros}

    def devolucao(self, devolucao_id: str) -> dict:
        """Uma devolução com os itens que ficaram gravados (sem recalcular nada)."""
        try:
            return self.contexto.devolucoes.por_id(devolucao_id)
        except KeyError:
            raise ErroAPI(
                HTTPStatus.NOT_FOUND, f"Devolução não encontrada: {devolucao_id}"
            ) from None

    def relatorio(self, nome: str, consulta: dict[str, list[str]]) -> dict:
        servico = ServicoExportacao(self.contexto)
        if nome == "estoque":
            relatorio = servico.relatorio_estoque()
        elif nome == "clientes":
            relatorio = servico.relatorio_clientes()
        elif nome == "crediario":
            relatorio = servico.relatorio_crediario()
        elif nome == "entradas":
            relatorio = servico.relatorio_entradas()
        elif nome == "auditoria":
            relatorio = servico.relatorio_auditoria()
        else:
            raise ErroAPI(HTTPStatus.NOT_FOUND, f"Relatório desconhecido: {nome}")
        return {
            "titulo": relatorio.titulo,
            "indicadores": [{"rotulo": rotulo, "valor": valor} for rotulo, valor in relatorio.indicadores],
            "tabelas": [
                {
                    "titulo": tabela.titulo,
                    "colunas": [coluna.titulo for coluna in tabela.colunas],
                    "linhas": [list(linha) for linha in tabela.linhas],
                }
                for tabela in relatorio.tabelas
            ],
            "avisos": list(relatorio.avisos),
        }

    # -- escrita ------------------------------------------------------------
    def cancelar_venda(self, venda_id: str, corpo: dict) -> dict:
        operador = self._autenticar(corpo.get("operador"), Acao.VENDA_CANCELAR)
        autorizador = self._autenticar(corpo.get("autorizador"), Acao.VENDA_CANCELAR)
        resultado = ServicoPDV(self.contexto).cancelar_venda(
            venda_id=venda_id,
            motivo=str(corpo.get("motivo") or ""),
            operador=operador,
            autorizador=autorizador,
            devolver_estoque=bool(corpo.get("devolver_estoque", True)),
        )
        return {"ok": True, "cancelamento": resultado}

    def registrar_devolucao(self, corpo: dict) -> dict:
        operador = self._autenticar(corpo.get("operador"), Acao.VENDA_DEVOLVER)
        autorizador = None
        if corpo.get("autorizador"):
            autorizador = self._autenticar(corpo["autorizador"], Acao.VENDA_DEVOLVER)
        itens = [
            ItemSolicitado(
                venda_item_sequencia=int(item["sequencia"]),
                quantidade=str(item["quantidade"]),
            )
            for item in corpo.get("itens") or []
        ]
        try:
            tipo = TipoDevolucao(str(corpo.get("tipo") or ""))
            destino = DestinoDevolucao(str(corpo.get("destino") or ""))
        except ValueError as exc:
            raise ErroAPI(
                HTTPStatus.BAD_REQUEST,
                "Tipo ou destino inválido.",
                {
                    "tipos": [tipo.value for tipo in TipoDevolucao],
                    "destinos": [destino.value for destino in DestinoDevolucao],
                },
            ) from exc
        resultado = ServicoDevolucao(self.contexto).registrar(
            operador=operador,
            venda_id=str(corpo.get("venda_id") or ""),
            itens=itens,
            tipo=tipo,
            destino=destino,
            motivo=str(corpo.get("motivo") or ""),
            autorizador=autorizador,
            caixa_id=corpo.get("caixa_id"),
            devolver_estoque=bool(corpo.get("devolver_estoque", True)),
            observacoes=str(corpo.get("observacoes") or ""),
        )
        return {
            "ok": True,
            "devolucao_id": resultado.devolucao_id,
            "total_centavos": resultado.total.centavos,
            "dinheiro_centavos": resultado.dinheiro_devolvido.centavos,
            "credito_centavos": resultado.credito_aplicado.centavos,
            "fora_do_prazo": resultado.prazo.exige_autorizacao,
            "avisos": list(resultado.avisos),
        }

    # -- escrita (rede multi-caixa, v0.14.0) --------------------------------
    def finalizar_venda(self, corpo: dict) -> dict:
        """Registra a venda pelo mesmo serviço da tela — nada recalculado aqui."""
        operador = self._autenticar(corpo.get("operador"), Acao.PDV_VENDER)
        autorizador = None
        if corpo.get("autorizador"):
            autorizador = self._autenticar(corpo["autorizador"], Acao.PDV_VENDER)
        caixa_id = str(corpo.get("caixa_id") or "")
        if not caixa_id:
            raise ErroAPI(HTTPStatus.BAD_REQUEST, "Informe caixa_id (o caixa do terminal).")
        carrinho = Carrinho()
        for item in corpo.get("itens") or []:
            codigo = str(item.get("codigo") or item.get("produto_id") or "")
            produto = self.contexto.produtos.buscar_leitura(codigo)
            desconto = item.get("desconto_centavos")
            carrinho.adicionar(
                produto,
                str(item.get("quantidade") or "1"),
                desconto=None
                if desconto in (None, "")
                else _dinheiro(desconto, "desconto_centavos"),
            )
        pagamentos = _plano_de_pagamentos(corpo.get("pagamentos"))
        resultado = ServicoPDV(self.contexto).finalizar_venda(
            SolicitacaoVenda(
                operador=operador,
                caixa_id=caixa_id,
                carrinho=carrinho,
                plano=pagamentos,
                cliente_id=corpo.get("cliente_id") or None,
                desconto_cupom=Dinheiro(int(corpo.get("desconto_cupom_centavos") or 0)),
                acrescimo=Dinheiro(int(corpo.get("acrescimo_centavos") or 0)),
                autorizador=autorizador,
                parcelas_crediario=int(corpo.get("parcelas_crediario") or 1),
                chave_idempotencia=str(corpo.get("chave_idempotencia") or uuid4()),
            )
        )
        return {
            "ok": True,
            "venda_id": resultado.venda.id,
            "rotulo": resultado.venda.rotulo,
            "total_centavos": resultado.venda.total.centavos,
            "terminal": self.terminal,
            "titulos": list(resultado.titulos),
            "ja_existia": resultado.ja_existia,
            "avisos": list(resultado.avisos),
        }

    def abrir_turno(self, corpo: dict) -> dict:
        operador = self._autenticar(corpo.get("operador"), Acao.CAIXA_ABRIR)
        fundo = _dinheiro(corpo.get("fundo_centavos"), "fundo_centavos")
        turno = ServicoCaixa(self.contexto).abrir_turno(
            caixa=str(corpo.get("caixa") or self.terminal),
            operador=operador,
            fundo=fundo,
        )
        return {
            "ok": True,
            "turno_id": turno.id,
            "caixa_id": turno.caixa_id,
            "terminal": turno.terminal_id or self.terminal,
            "fundo_centavos": fundo.centavos,
            "esperado_centavos": self.contexto.caixas.carregar_turno(turno.id).esperado.centavos,
        }

    def turnos(self, consulta: dict[str, list[str]]) -> dict:
        abertos = self.contexto.caixas.turnos_abertos()
        return {
            "total": len(abertos),
            "itens": [
                {
                    "turno_id": turno.id,
                    "caixa_id": turno.caixa_id,
                    "terminal": turno.terminal_id,
                    "operador_id": turno.operador_id,
                    "aberto_em": turno.aberto_em,
                    "fundo_centavos": turno.fundo.centavos,
                }
                for turno in abertos
            ],
        }

    def fechar_turno(self, turno_id: str, corpo: dict) -> dict:
        conferente = self._autenticar(corpo.get("operador"), Acao.CAIXA_FECHAR)
        contagens = [
            ContagemDenominacao(
                denominacao=int(item["denominacao"]), quantidade=int(item["quantidade"])
            )
            for item in corpo.get("contagens") or []
        ]
        resultado = ServicoCaixa(self.contexto).fechar_turno(
            turno_id=turno_id,
            conferente=conferente,
            contagens=contagens,
            motivo_diferenca=str(corpo.get("motivo_diferenca") or ""),
        )
        return {
            "ok": True,
            "turno_id": resultado.turno.id,
            "conferencia": resultado.conferencia,
            "avisos": list(resultado.avisos),
        }

    def receber_titulo(self, titulo_id: str, corpo: dict) -> dict:
        operador = self._autenticar(corpo.get("operador"), Acao.TITULO_RECEBER)
        autorizador = None
        if corpo.get("autorizador"):
            autorizador = self._autenticar(corpo["autorizador"], Acao.TITULO_RECEBER)
        resultado = ServicoCrediario(self.contexto).receber(
            titulo_id=titulo_id,
            valor=_dinheiro(corpo.get("valor_centavos"), "valor_centavos"),
            forma=_forma(corpo.get("forma")),
            operador=operador,
            caixa_id=str(corpo.get("caixa_id") or ""),
            referencia=str(corpo.get("referencia") or ""),
            cobrar_encargos=bool(corpo.get("cobrar_encargos", True)),
            motivo_dispensa=str(corpo.get("motivo_dispensa") or ""),
            autorizador=autorizador,
        )
        return {
            "ok": True,
            "recebimento_id": resultado.recebimento_id,
            "saldo_restante_centavos": resultado.saldo_restante.centavos,
            "encargo_centavos": resultado.encargo.centavos,
            "multa_centavos": resultado.multa.centavos,
            "juros_centavos": resultado.juros.centavos,
            "dias_atraso": resultado.dias_atraso,
            "encargos_dispensados": resultado.encargos_dispensados,
        }

    def lancar_entrada(self, corpo: dict) -> dict:
        operador = self._autenticar(corpo.get("operador"), Acao.ESTOQUE_ENTRADA)
        itens: list[ItemEntrada] = []
        for item in corpo.get("itens") or []:
            produto = self.contexto.produtos.buscar_leitura(
                str(item.get("codigo") or item.get("produto_id") or "")
            )
            itens.append(
                ItemEntrada(
                    produto_id=produto.id,
                    codigo=produto.codigo,
                    quantidade=Quantidade.de_unidades(str(item.get("quantidade") or "0")),
                    custo_unitario=Dinheiro(int(item.get("custo_unitario_centavos") or 0)),
                )
            )
        entrada = EntradaMercadoria(
            fornecedor=str(corpo.get("fornecedor") or ""),
            documento=str(corpo.get("documento") or ""),
            itens=tuple(itens),
            frete=Dinheiro(int(corpo.get("frete_centavos") or 0)),
        )
        return {"ok": True, **ServicoEstoque(self.contexto).registrar_entrada(
            operador=operador, entrada=entrada
        )}

    def _autenticar(self, credenciais: Any, acao: Acao) -> Any:
        if not isinstance(credenciais, dict) or not credenciais.get("login"):
            raise ErroAPI(
                HTTPStatus.UNAUTHORIZED,
                "Informe operador.login e operador.senha no corpo da requisição.",
            )
        try:
            return ServicoAutenticacao(self.contexto).autorizar(
                str(credenciais["login"]), str(credenciais.get("senha") or ""), acao
            )
        except ErroBussola as exc:
            raise ErroAPI(HTTPStatus.UNAUTHORIZED, str(exc)) from exc


def _dinheiro(valor: Any, campo: str) -> Dinheiro:
    """Centavos como inteiro. Texto com vírgula também é aceito (bilhete do operador)."""
    if valor is None or valor == "":
        raise ErroAPI(HTTPStatus.BAD_REQUEST, f"Informe {campo} em centavos.")
    if isinstance(valor, str) and "," in valor:
        inteiro, _, centavos = valor.replace("R$", "").strip().partition(",")
        return Dinheiro(int(inteiro.replace(".", "") or 0) * 100 + int(centavos.ljust(2, "0")[:2]))
    try:
        return Dinheiro(int(valor))
    except (TypeError, ValueError) as exc:
        raise ErroAPI(HTTPStatus.BAD_REQUEST, f"{campo} precisa ser inteiro (centavos).") from exc


def _forma(valor: Any) -> FormaPagamento:
    try:
        return FormaPagamento(str(valor or "DINHEIRO").upper())
    except ValueError as exc:
        raise ErroAPI(
            HTTPStatus.BAD_REQUEST,
            "Forma de pagamento inválida.",
            {"formas": [forma.value for forma in FormaPagamento]},
        ) from exc


def _plano_de_pagamentos(pagamentos: Any) -> PlanoPagamento:
    """Aceita `[{"forma": "DINHEIRO", "valor_centavos": 1000}]` (até três formas).

    `A_PRAZO` é o crediário: gera título, não entra na gaveta. As demais formas
    eletrônicas nascem **pendentes**, exatamente como na tela — a API não inventa
    uma confirmação que a adquirente não mandou.
    """
    if not isinstance(pagamentos, list) or not pagamentos:
        raise ErroAPI(
            HTTPStatus.BAD_REQUEST,
            "Informe pagamentos:[{forma, valor_centavos}] (use A_PRAZO para crediário).",
        )
    linhas: list[Pagamento] = []
    for item in pagamentos:
        if not isinstance(item, dict):
            raise ErroAPI(HTTPStatus.BAD_REQUEST, "Cada pagamento precisa ser um objeto.")
        forma = _forma(item.get("forma"))
        valor = _dinheiro(item.get("valor_centavos"), "valor_centavos")
        if forma is FormaPagamento.A_PRAZO:
            linhas.append(pagamento_a_prazo(valor))
        elif forma is FormaPagamento.DINHEIRO:
            entregue = item.get("valor_entregue_centavos")
            linhas.append(
                pagamento_dinheiro(
                    valor,
                    None if entregue is None else _dinheiro(entregue, "valor_entregue_centavos"),
                )
            )
        else:
            linhas.append(
                pagamento_eletronico(
                    forma,
                    valor,
                    confirmado=bool(item.get("confirmado", False)),
                    referencia=str(item.get("referencia") or ""),
                )
            )
    return PlanoPagamento.de_pagamentos(*linhas)


def _fabrica(contexto: Contexto | Callable[[], Contexto]) -> Callable[[], Contexto]:
    """Aceita um contexto já aberto (base em arquivo) ou uma fábrica de contexto."""
    if callable(contexto):
        return contexto
    caminho = contexto.caminho
    if caminho is None:
        raise ErroAPI(
            HTTPStatus.BAD_REQUEST,
            "A API precisa de base em arquivo: base em memória não atravessa threads.",
        )
    return lambda: Contexto.abrir(caminho, relogio=contexto.relogio)


class _Manipulador(BaseHTTPRequestHandler):
    servico: ServicoWeb  # injetado por ServidorAPI
    server_version = "BussolaPDV-API/1"
    sys_version = ""

    # -- infraestrutura HTTP ------------------------------------------------
    def log_message(self, formato: str, *args: object) -> None:  # silencia o stderr do stdlib
        return

    def _responder(self, status: int, corpo: dict) -> None:
        conteudo = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(conteudo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(conteudo)

    def _token_ok(self) -> bool:
        esperado = f"Bearer {self.servico.configuracao.token}"
        return self.headers.get("Authorization", "") == esperado

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho <= 0:
            return {}
        try:
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ErroAPI(HTTPStatus.BAD_REQUEST, "Corpo JSON inválido.") from exc
        if not isinstance(dados, dict):
            raise ErroAPI(HTTPStatus.BAD_REQUEST, "O corpo precisa ser um objeto JSON.")
        return dados

    def _despachar(self, metodo: str) -> None:
        inicio = time.monotonic()
        status_final = HTTPStatus.OK
        pedido_por = ""
        # O terminal se identifica por cabeçalho; sem ele vale o padrão do servidor.
        self.servico.terminal = self.headers.get("X-Bussola-Terminal", "")
        if not self._token_ok():
            self._responder(
                HTTPStatus.UNAUTHORIZED,
                {"erro": "Token ausente ou inválido (Authorization: Bearer ...)."},
            )
            self._registrar_acesso(metodo, HTTPStatus.UNAUTHORIZED, inicio, pedido_por)
            return
        caminho = self.path
        consulta = parse_qs(urlparse(caminho).query)
        try:
            corpo = self._corpo() if metodo in {"POST", "PUT", "PATCH"} else {}
            resposta = self.servico.tratar(metodo, caminho, consulta, corpo)
        except ErroAPI as exc:
            status_final = exc.status
            self._responder(exc.status, {"erro": exc.mensagem, "detalhe": exc.detalhe})
            return
        except ErroNaoEncontrado as exc:
            status_final = HTTPStatus.NOT_FOUND
            self._responder(HTTPStatus.NOT_FOUND, {"erro": str(exc)})
            return
        except ErroValidacao as exc:
            status_final = HTTPStatus.UNPROCESSABLE_ENTITY
            self._responder(HTTPStatus.UNPROCESSABLE_ENTITY, {"erro": str(exc)})
            return
        except ErroBussola as exc:
            status_final = HTTPStatus.CONFLICT
            self._responder(HTTPStatus.CONFLICT, {"erro": str(exc)})
            return
        except Exception as exc:  # nunca vazar stack trace para o cliente
            status_final = HTTPStatus.INTERNAL_SERVER_ERROR
            self._responder(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"erro": "Erro interno na API.", "tipo": type(exc).__name__},
            )
            return
        finally:
            self._registrar_acesso(metodo, status_final, inicio, pedido_por)
        self._responder(HTTPStatus.OK, resposta)

    def _registrar_acesso(
        self, metodo: str, status: int, inicio: float, pedido_por: str
    ) -> None:
        """Uma linha JSONL por requisição — quem chamou, de onde, o que respondeu.

        Serve para o dia em que dois caixas disputarem uma venda: o log mostra o
        terminal, o instante e o código. Silencioso se não houver arquivo configurado.
        """
        destino = self.servico.configuracao.log_acesso
        if not destino:
            return
        linha = {
            "quando": datetime.now(UTC).isoformat(timespec="seconds"),
            "terminal": self.servico.terminal,
            "ip": self.client_address[0] if self.client_address else "",
            "metodo": metodo,
            "rota": urlparse(self.path).path,
            "status": int(status),
            "ms": round((time.monotonic() - inicio) * 1000, 1),
        }
        if pedido_por:
            linha["operador"] = pedido_por
        try:
            with open(destino, "a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError:  # log não pode derrubar a venda
            return

    def do_GET(self) -> None:
        self._despachar("GET")

    def do_POST(self) -> None:
        self._despachar("POST")


class ServidorAPI:
    """Servidor HTTP em thread própria — o programa pode seguir aberto."""

    def __init__(
        self,
        contexto: Contexto | Callable[[], Contexto],
        configuracao: ConfiguracaoAPI,
    ) -> None:
        if len(configuracao.token) < 16:
            raise ErroAPI(
                HTTPStatus.BAD_REQUEST, "O token precisa de pelo menos 16 caracteres."
            )
        self.configuracao = configuracao
        self.servico = ServicoWeb(fabrica=_fabrica(contexto), configuracao=configuracao)
        manipulador = type(
            "ManipuladorBussola",
            (_Manipulador,),
            {"servico": self.servico},
        )
        self._http = ThreadingHTTPServer((configuracao.host, configuracao.porta), manipulador)
        self._http.daemon_threads = True
        if configuracao.tls is not None:
            # O socket é embrulhado ANTES de servir: daí em diante tudo é TLS.
            self._http.socket = configuracao.tls.contexto_tls().wrap_socket(
                self._http.socket, server_side=True
            )
        self._thread: threading.Thread | None = None

    # -- ciclo de vida ------------------------------------------------------
    @property
    def porta(self) -> int:
        return int(self._http.server_address[1])

    @property
    def endereco(self) -> str:
        host = str(self._http.server_address[0])
        porta = int(self._http.server_address[1])
        esquema = "https" if self.configuracao.tls is not None else "http"
        return f"{esquema}://{host}:{porta}/{VERSAO_API}"

    @property
    def digital_do_certificado(self) -> str:
        """Impressão digital para o operador conferir no terminal (ou vazio)."""
        if self.configuracao.tls is None:
            return ""
        return str(getattr(self.configuracao.tls, "digital", ""))

    def iniciar(self) -> ServidorAPI:
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()
        return self

    def parar(self) -> None:
        self._http.shutdown()
        self._http.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> ServidorAPI:
        return self.iniciar()

    def __exit__(self, *_: object) -> None:
        self.parar()


__all__ = [
    "VERSAO_API",
    "ConfiguracaoAPI",
    "ErroAPI",
    "ServicoWeb",
    "ServidorAPI",
]
