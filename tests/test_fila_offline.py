"""Fila local de vendas quando a rede cai (ADR-036).

Três perguntas que este arquivo responde com teste, e não com promessa:

1. **a venda fica guardada?** servidor fora do ar, `finalizar_venda` levanta
   `VendaGuardadaParaEnvio` e a venda aparece na fila local com a chave;
2. **reenviar duplica?** não. A chave de idempotência já existia para duplo
   clique; é ela que protege o reenvio. O teste começa a venda, "perde" a
   resposta e reenvia o mesmo pedido: o servidor devolve a venda original;
3. **e quando o servidor recusa por regra?** a venda **não** é apagada: fica na
   fila como `RECUSADA`, com o motivo escrito, para alguém decidir. Rede fora é
   uma coisa; estoque que acabou é outra.

O que a fila **não** faz, e o teste guarda: aceitar venda pendente de outro
operador. Quem fez a venda é quem reenvia.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.estoque import ServicoEstoque
from bussola_pdv.aplicacao.fila_offline import FilaDeVendas, reenviar
from bussola_pdv.aplicacao.pdv import SolicitacaoVenda
from bussola_pdv.aplicacao.remoto import (
    ContextoRemoto,
    VendaGuardadaParaEnvio,
    servicos_de,
)
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.estoque import TipoMovimentoEstoque
from bussola_pdv.dominio.pagamentos import FormaPagamento, Pagamento, PlanoPagamento
from bussola_pdv.dominio.relogio import RelogioFixo
from bussola_pdv.dominio.seguranca import gerar_hash
from bussola_pdv.dominio.usuario import Perfil, Usuario
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.api.cliente import ClienteAPI
from bussola_pdv.infra.api.servidor import ConfiguracaoAPI, ServidorAPI
from bussola_pdv.infra.rede.configuracao_terminal import ConfiguracaoRemota
from bussola_pdv.infra.sqlite.repositorio_estoque import EstoqueRepositorio

SENHA = "senha-de-teste"
TOKEN = "token-da-fila-1234567890"
INSTANTE = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def _porta_livre() -> int:
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        return int(sonda.getsockname()[1])


@pytest.fixture
def ambiente(tmp_path: Path):
    hash_senha = gerar_hash(SENHA)
    contexto = Contexto.abrir(tmp_path / "servidor.db", relogio=RelogioFixo(INSTANTE))
    master = Usuario(login="master", nome="Dora", perfil=Perfil.ADMIN_MASTER, senha_hash=hash_senha)
    operador = Usuario(
        login="operador", nome="Carla", perfil=Perfil.ATENDENTE, senha_hash=hash_senha
    )
    gerente = Usuario(login="gerente", nome="Bruno", perfil=Perfil.GERENTE, senha_hash=hash_senha)
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
    porta = _porta_livre()
    pasta = tmp_path / "caixa"
    pasta.mkdir()
    configuracao = ConfiguracaoRemota(
        endereco=f"http://127.0.0.1:{porta}", token=TOKEN, terminal="CAIXA-02"
    )

    def subir() -> ServidorAPI:
        servidor = ServidorAPI(
            contexto, ConfiguracaoAPI(token=TOKEN, porta=porta, terminal="SERVIDOR")
        )
        servidor.iniciar()
        return servidor

    yield {
        "contexto": contexto,
        "produto": produto,
        "turno": turno,
        "porta": porta,
        "pasta": pasta,
        "configuracao": configuracao,
        "subir": subir,
        "servidores": [],
    }
    contexto.fechar()


def _cliente(ambiente, *, operador: str = "operador") -> ClienteAPI:
    cliente = ClienteAPI(pasta=ambiente["pasta"], configuracao=ambiente["configuracao"])
    cliente.abrir_sessao(operador, SENHA)
    return cliente


def _solicitacao(ambiente, cliente: ClienteAPI, quantidade: int = 1) -> SolicitacaoVenda:
    produto = cliente.executar("consultas", "produto_para_leitura", {"entrada": "A001"})
    carrinho = Carrinho()
    carrinho.adicionar(produto, quantidade)
    total = 1590 * quantidade
    return SolicitacaoVenda(
        operador=cliente.operador,
        caixa_id=ambiente["turno"].caixa_id,
        carrinho=carrinho,
        plano=PlanoPagamento(
            (
                Pagamento(
                    forma=FormaPagamento.DINHEIRO,
                    valor_aplicado=Dinheiro(total),
                    valor_entregue=Dinheiro(total),
                ),
            )
        ),
    )


def test_venda_com_rede_fora_vai_para_a_fila(ambiente) -> None:
    servidor = ambiente["subir"]()
    ambiente["servidores"].append(servidor)
    cliente = _cliente(ambiente)
    solicitacao = _solicitacao(ambiente, cliente)
    servidor.parar()

    servicos = servicos_de(ContextoRemoto(cliente))
    with pytest.raises(VendaGuardadaParaEnvio) as erro:
        servicos.pdv.finalizar_venda(solicitacao)

    assert erro.value.chave == solicitacao.chave_idempotencia
    assert erro.value.quantidade == 1
    fila = FilaDeVendas(ambiente["pasta"] / "vendas-pendentes.db")
    assert fila.quantidade() == 1
    pendente = fila.obter(solicitacao.chave_idempotencia)
    assert pendente.status == "PENDENTE"
    assert pendente.terminal == "CAIXA-02"
    assert pendente.operador_login == "operador"
    fila.fechar()


def test_reenvio_quando_o_servidor_volta(ambiente) -> None:
    servidor = ambiente["subir"]()
    cliente = _cliente(ambiente)
    solicitacao = _solicitacao(ambiente, cliente, 2)
    servidor.parar()
    servicos = servicos_de(ContextoRemoto(cliente))
    with pytest.raises(VendaGuardadaParaEnvio):
        servicos.pdv.finalizar_venda(solicitacao)

    ambiente["servidores"].append(ambiente["subir"]())  # a rede voltou
    # servidor reiniciado derruba a sessão: o operador entra de novo antes de reenviar
    cliente.abrir_sessao("operador", SENHA)
    fila = FilaDeVendas(ambiente["pasta"] / "vendas-pendentes.db")
    resultado = reenviar(
        fila, cliente, solicitacao_tipo=SolicitacaoVenda, operador_id=cliente.operador.id
    )
    assert resultado.enviadas == 1
    assert resultado.recusadas == 0
    assert fila.quantidade() == 0

    linha = ambiente["contexto"].conexao.execute(
        "SELECT total_centavos, terminal_id FROM vendas WHERE chave_idempotencia = ?",
        (solicitacao.chave_idempotencia,),
    ).fetchone()
    assert linha["total_centavos"] == 3180
    assert linha["terminal_id"] == "CAIXA-02"
    fila.fechar()


def test_reenviar_o_mesmo_pedido_nao_duplica(ambiente) -> None:
    ambiente["servidores"].append(ambiente["subir"]())
    cliente = _cliente(ambiente)
    servicos = servicos_de(ContextoRemoto(cliente))
    solicitacao = _solicitacao(ambiente, cliente)
    primeira = servicos.pdv.finalizar_venda(solicitacao)
    segunda = servicos.pdv.finalizar_venda(solicitacao)  # como se a resposta tivesse sumido
    assert segunda.ja_existia is True
    assert segunda.venda.id == primeira.venda.id
    total = ambiente["contexto"].conexao.execute(
        "SELECT COUNT(*) AS total FROM vendas"
    ).fetchone()["total"]
    assert total == 1


def test_recusa_de_negocio_marca_pendencia_sem_apagar(ambiente) -> None:
    ambiente["servidores"].append(ambiente["subir"]())
    cliente = _cliente(ambiente)
    servicos = servicos_de(ContextoRemoto(cliente))
    grande = _solicitacao(ambiente, cliente, 500)  # não há 500 unidades
    fila = servicos.fila

    # sem rede, a venda grande é guardada
    for servidor in ambiente["servidores"]:
        servidor.parar()
    with pytest.raises(VendaGuardadaParaEnvio):
        servicos.pdv.finalizar_venda(grande)
    assert fila.quantidade() == 1

    ambiente["servidores"].append(ambiente["subir"]())
    cliente.abrir_sessao("operador", SENHA)
    resultado = reenviar(
        fila, cliente, solicitacao_tipo=SolicitacaoVenda, operador_id=cliente.operador.id
    )
    assert resultado.recusadas == 1
    pendente = fila.obter(grande.chave_idempotencia)
    assert pendente.status == "RECUSADA"
    assert pendente.motivo
    assert pendente.precisa_de_atencao is True
    # continua na fila: quem decide é a loja, não o programa
    assert fila.quantidade() == 1
    assert fila.descartar(grande.chave_idempotencia) is True
    assert fila.quantidade() == 0


def test_reenvio_exige_o_mesmo_operador(ambiente) -> None:
    servidor = ambiente["subir"]()
    cliente = _cliente(ambiente)
    solicitacao = _solicitacao(ambiente, cliente)
    servidor.parar()
    with pytest.raises(VendaGuardadaParaEnvio):
        servicos_de(ContextoRemoto(cliente)).pdv.finalizar_venda(solicitacao)

    ambiente["servidores"].append(ambiente["subir"]())
    outro = _cliente(ambiente, operador="gerente")
    fila = FilaDeVendas(ambiente["pasta"] / "vendas-pendentes.db")
    resultado = reenviar(
        fila, outro, solicitacao_tipo=SolicitacaoVenda, operador_id=outro.operador.id
    )
    assert resultado.enviadas == 0
    assert resultado.continuam_pendentes == 1
    assert "só quem fez a venda" in resultado.mensagens[0]
    assert fila.quantidade() == 1
    fila.fechar()
