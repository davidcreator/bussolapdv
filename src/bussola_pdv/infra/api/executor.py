"""Execução de um caso de uso a pedido de um terminal (modo remoto, ADR-036).

O terminal não tem banco, não tem repositório e não decide nada: ele manda
"serviço X, método Y, com estes argumentos" e o servidor executa **o mesmo
objeto de aplicação** que a tela local executaria, com o usuário da sessão.
Isso é o que faz a janela completa funcionar pela rede sem reescrever tela por
tela — e é também o que mantém uma única verdade sobre regra de negócio.

O que este módulo protege:

1. **Só métodos públicos e de serviço.** Nome de serviço precisa estar na
   tabela; método precisa ser público e existir. Nada de `__init__`, nada de
   atributo, nada de importar módulo por nome vindo da rede.
2. **Identidade vem do servidor.** Todo argumento `Usuario` de papel **de ator**
   (`usuario`, `operador`, `autor`, `ator`) é substituído pelo usuário da
   sessão; `autorizador` só é aceito com credencial emitida pelo próprio
   servidor. Um terminal não escolhe quem é.
3. **Alvo não é ator.** Parâmetro `Usuario` com outro nome (o usuário que se
   está alterando, por exemplo) é carregado pelo id — é dado, não identidade.
4. **Erro do domínio volta como erro do domínio.** O terminal recebe o tipo e a
   mensagem, e a tela mostra exatamente o que mostraria localmente.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path
from typing import Any

from ...aplicacao.administracao import ServicoAdministracao
from ...aplicacao.autenticacao import ServicoAutenticacao
from ...aplicacao.backup import ServicoBackup
from ...aplicacao.caixa import ServicoCaixa
from ...aplicacao.clientes import ServicoClientes
from ...aplicacao.contexto import Contexto
from ...aplicacao.crediario import ServicoCrediario
from ...aplicacao.devolucao import ServicoDevolucao
from ...aplicacao.estoque import ServicoEstoque
from ...aplicacao.exportacao import ServicoExportacao
from ...aplicacao.impressao import ServicoImpressao
from ...aplicacao.marca import ServicoMarca
from ...aplicacao.parametros import ServicoParametros
from ...aplicacao.pdv import ServicoPDV
from ...aplicacao.permissoes import ServicoPermissoes
from ...aplicacao.relatorios import ServicoRelatorios
from ...aplicacao.usuarios import ServicoUsuarios
from ...dominio.auditoria import EventoAuditoria, ResultadoVerificacao
from ...dominio.caixa import MovimentoCaixa, Turno
from ...dominio.cliente import Cliente
from ...dominio.erros import AutorizacaoNegada, ErroBussola, ErroValidacao
from ...dominio.produto import Produto
from ...dominio.usuario import Usuario
from ..sqlite.repositorio_caixa import TurnoRegistrado
from ..sqlite.repositorio_vendas import VendaRegistrada
from .contrato import (
    ErroDeContrato,
    _resolver,
    assinatura_remota,
    codificar,
    decodificar,
)
from .sessao import ArmazemDeSessoes, Sessao


class Consultas:
    """Leituras que a tela local faz direto no repositório e o terminal pede aqui.

    Não são "SQL por HTTP": é uma lista fechada de consultas de leitura que a
    interface já fazia e que não existem como caso de uso (listar caixas,
    carregar turno para conferir, ler um parâmetro para pintar a tela). Cada uma
    é um método nomeado, com tipo de retorno — nada genérico, nada arbitrário.
    """

    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- caixa --------------------------------------------------------------
    def listar_caixas(self) -> list[dict[str, str]]:
        return self.ctx.caixas.listar_caixas()

    def turno_aberto(self, caixa_id: str) -> TurnoRegistrado | None:
        return self.ctx.caixas.turno_aberto(caixa_id)

    def carregar_turno(self, turno_id: str) -> Turno:
        return self.ctx.caixas.carregar_turno(turno_id)

    def movimentos(self, turno_id: str) -> list[MovimentoCaixa]:
        return self.ctx.caixas.movimentos(turno_id)

    # -- parâmetros ---------------------------------------------------------
    def parametro(self, chave: str) -> str:
        return self.ctx.parametros.obter(chave)

    def parametro_int(self, chave: str) -> int:
        return self.ctx.parametros.obter_int(chave)

    def parametro_bool(self, chave: str) -> bool:
        return self.ctx.parametros.obter_bool(chave)

    def parametros_por_prefixo(self, prefixo: str) -> dict[str, str]:
        return self.ctx.parametros.por_prefixo(prefixo)

    # -- produtos -----------------------------------------------------------
    def produtos_listar(
        self,
        busca: str = "",
        categoria: str = "",
        apenas_ativos: bool = True,
        limite: int = 500,
    ) -> list[Produto]:
        return self.ctx.produtos.listar(
            busca=busca, categoria=categoria, apenas_ativos=apenas_ativos, limite=limite
        )

    def produto_por_id(self, produto_id: str) -> Produto:
        return self.ctx.produtos.por_id(produto_id)

    def produto_por_codigo(self, codigo: str) -> Produto:
        return self.ctx.produtos.por_codigo(codigo)

    def produto_para_leitura(self, entrada: str) -> Produto:
        return self.ctx.produtos.buscar_leitura(entrada)

    def saldos(self, produtos_ids: list[str] | None = None) -> dict[str, int]:
        return self.ctx.produtos.saldos(produtos_ids)

    # -- clientes -----------------------------------------------------------
    def clientes(self, busca: str = "", limite: int = 500) -> list[Cliente]:
        return self.ctx.clientes.listar(busca=busca, limite=limite)

    # -- vendas -------------------------------------------------------------
    def venda_por_id(self, venda_id: str) -> VendaRegistrada:
        return self.ctx.vendas.por_id(venda_id)

    def vendas(
        self,
        data_inicial: str | None = None,
        data_final: str | None = None,
        operador_id: str | None = None,
        turno_id: str | None = None,
        limite: int = 200,
    ) -> list[dict]:
        return self.ctx.vendas.listar(
            data_inicial=data_inicial,
            data_final=data_final,
            operador_id=operador_id,
            turno_id=turno_id,
            limite=limite,
        )

    # -- entradas e auditoria ----------------------------------------------
    def entradas(self, limite: int = 200) -> list[dict]:
        return self.ctx.entradas.listar(limite=limite)

    def auditoria(
        self, limite: int = 200, data_negocio: str | None = None
    ) -> list[EventoAuditoria]:
        return self.ctx.auditoria.listar(limite=limite, data_negocio=data_negocio)

    def auditoria_verificar(self) -> ResultadoVerificacao:
        return self.ctx.auditoria.verificar()

    # -- usuários -----------------------------------------------------------
    def usuario_por_id(self, usuario_id: str) -> Usuario:
        return self.ctx.usuarios.por_id(usuario_id)

    def usuario_por_login(self, login: str) -> Usuario:
        return self.ctx.usuarios.por_login(login)

    def usuarios(self) -> list[Usuario]:
        return self.ctx.usuarios.listar()


#: Serviços que podem ser chamados por um terminal. Lista fechada de propósito.
SERVICOS: dict[str, type] = {
    "administracao": ServicoAdministracao,
    "consultas": Consultas,
    "autenticacao": ServicoAutenticacao,
    "backup": ServicoBackup,
    "caixa": ServicoCaixa,
    "clientes": ServicoClientes,
    "crediario": ServicoCrediario,
    "devolucao": ServicoDevolucao,
    "estoque": ServicoEstoque,
    "exportacao": ServicoExportacao,
    "impressao": ServicoImpressao,
    "marca": ServicoMarca,
    "parametros": ServicoParametros,
    "pdv": ServicoPDV,
    "permissoes": ServicoPermissoes,
    "relatorios": ServicoRelatorios,
    "usuarios": ServicoUsuarios,
}

#: Nomes de parâmetro (em qualquer profundidade) que significam **ator**.
PAPEIS_DE_ATOR = frozenset({"usuario", "operador", "autor", "ator"})


class ErroDeExecucao(ErroValidacao):
    """Pedido malformado para o executor (não é erro de regra de negócio)."""


def servico(nome: str) -> type:
    try:
        return SERVICOS[nome]
    except KeyError:
        raise ErroDeExecucao(
            f"Serviço desconhecido: {nome!r}. Disponíveis: {', '.join(sorted(SERVICOS))}."
        ) from None


def executar(
    contexto: Contexto,
    sessao: Sessao,
    usuario: Usuario,
    nome_servico: str,
    nome_metodo: str,
    argumentos: dict[str, Any],
    *,
    credenciais: ArmazemDeSessoes,
) -> Any:
    """Decodifica, injeta identidade, executa e devolve o resultado pronto para JSON."""
    classe = servico(nome_servico)
    método = getattr(classe, nome_metodo, None)
    if nome_metodo.startswith("_") or not callable(método):
        raise ErroDeExecucao(f"{nome_servico}.{nome_metodo} não é um caso de uso público.")

    anotações = _resolver(classe, nome_metodo)
    parâmetros = {p.name: p for p in assinatura_remota(classe, nome_metodo).parameters.values()}

    convertidos: dict[str, Any] = {}
    for nome, valor in (argumentos or {}).items():
        parâmetro = parâmetros.get(nome)
        if parâmetro is None:
            if any(p.kind is p.VAR_KEYWORD for p in parâmetros.values()):
                convertidos[nome] = valor
                continue
            raise ErroDeExecucao(f"{nome_servico}.{nome_metodo} não aceita o argumento {nome!r}.")
        convertidos[nome] = decodificar(valor, anotações.get(nome, parâmetro.annotation))

    _exigir_obrigatorios(nome_servico, nome_metodo, parâmetros, convertidos, anotações)
    convertidos = {
        nome: _caminho_do_servidor(contexto, valor) if isinstance(valor, Path) else valor
        for nome, valor in convertidos.items()
    }
    convertidos = _resolver_usuarios(convertidos, contexto, sessao, usuario, credenciais)

    instância = classe(contexto)
    retorno = getattr(instância, nome_metodo)(**convertidos)
    return codificar(retorno)


def _exigir_obrigatorios(
    nome_servico: str,
    nome_metodo: str,
    parâmetros: dict[str, Any],
    convertidos: dict[str, Any],
    anotações: dict[str, Any],
) -> None:
    """Argumento obrigatório ausente é erro do pedido (400), não erro interno (500).

    Sem isto, um campo faltando viraria `TypeError` no meio do caso de uso e o
    operador leria "erro interno na API" em vez de "falta o valor".
    """
    faltando: list[str] = []
    for nome, parâmetro in parâmetros.items():
        if parâmetro.kind in (parâmetro.VAR_KEYWORD, parâmetro.VAR_POSITIONAL):
            continue
        if anotações.get(nome) is Usuario or nome == "autorizador":
            continue  # o servidor injeta
        if parâmetro.default is inspect.Parameter.empty and nome not in convertidos:
            faltando.append(nome)
    if faltando:
        raise ErroDeExecucao(
            f"{nome_servico}.{nome_metodo} precisa de: {', '.join(sorted(faltando))}."
        )


def pasta_de_relatorios(contexto: Contexto) -> Path:
    """Onde o servidor grava relatório exportado (ao lado da base)."""
    base = contexto.caminho.parent if contexto.caminho is not None else Path.cwd()
    return base / "relatorios"


def _caminho_do_servidor(contexto: Contexto, destino: Path) -> Path:
    r"""Um `Path` vindo do terminal é sempre **nome de arquivo** aqui.

    O terminal não escolhe pasta no servidor: ele sugere o nome, e o servidor
    grava na própria pasta de relatórios. Sem isso, um terminal poderia mandar
    `C:\Windows\...` e o servidor obedeceria.
    """
    nome = Path(str(destino)).name
    if not nome or nome in {".", ".."} or "\\" in nome or "/" in nome:
        raise ErroDeExecucao(f"Nome de arquivo inválido: {destino!s}.")
    return pasta_de_relatorios(contexto) / nome


def _resolver_usuarios(
    valor: Any,
    contexto: Contexto,
    sessao: Sessao,
    usuario: Usuario,
    credenciais: ArmazemDeSessoes,
    *,
    papel: str = "",
) -> Any:
    """Troca toda referência de usuário pela identidade que o servidor reconhece."""
    tipo = type(valor)
    if tipo.__name__ == "UsuarioRemoto":
        return _resolver_referencia(valor, contexto, sessao, usuario, credenciais, papel)

    if isinstance(valor, (list, tuple)):
        itens = [
            _resolver_usuarios(item, contexto, sessao, usuario, credenciais, papel=papel)
            for item in valor
        ]
        return tuple(itens) if isinstance(valor, tuple) else itens
    if isinstance(valor, dict):
        return {
            chave: _resolver_usuarios(item, contexto, sessao, usuario, credenciais, papel=chave)
            for chave, item in valor.items()
        }
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        trocas: dict[str, Any] = {}
        for campo in dataclasses.fields(valor):
            atual = getattr(valor, campo.name)
            if atual is None:
                continue
            convertido = _resolver_usuarios(
                atual, contexto, sessao, usuario, credenciais, papel=campo.name
            )
            if convertido is not atual:
                trocas[campo.name] = convertido
        return dataclasses.replace(valor, **trocas) if trocas else valor
    return valor


def _resolver_referencia(
    referência: Any,
    contexto: Contexto,
    sessao: Sessao,
    usuario: Usuario,
    credenciais: ArmazemDeSessoes,
    papel: str,
) -> Usuario:
    identificador = str(getattr(referência, "id", ""))
    credencial = str(getattr(referência, "credencial", "") or "")

    if papel in PAPEIS_DE_ATOR or papel == "autorizador":
        if credencial:
            autorizado = credenciais.obter(credencial)
            if autorizado is None:
                raise AutorizacaoNegada(
                    "A autorização expirou. Peça para o gerente digitar a senha novamente."
                )
            if autorizado.usuario_id != identificador:
                raise AutorizacaoNegada("A credencial não pertence ao usuário informado.")
            carregado = _por_id(contexto, identificador)
            if carregado is None:  # pragma: no cover - usuário apagado no meio do caminho
                raise AutorizacaoNegada("Autorizador não encontrado.")
            return carregado
        if papel == "autorizador":
            raise AutorizacaoNegada(
                "Esta operação exige autorização com senha de gerente ou administrador."
            )
        if identificador and identificador != usuario.id:
            raise AutorizacaoNegada("O terminal não pode agir em nome de outro usuário.")
        return usuario

    # Alvo (dado): carregado pelo id, nunca tratado como identidade.
    carregado = _por_id(contexto, identificador)
    if carregado is None:
        raise ErroValidacao(f"Usuário não encontrado: {identificador}.")
    return carregado


def _por_id(contexto: Contexto, identificador: str) -> Usuario | None:
    if not identificador:
        return None
    try:
        return contexto.usuarios.por_id(identificador)
    except ErroBussola:
        return None


def capacidades() -> dict[str, list[str]]:
    """Serviço → métodos públicos, para o terminal conferir a versão do servidor."""
    saida: dict[str, list[str]] = {}
    for nome, classe in SERVICOS.items():
        métodos = [
            atributo
            for atributo in dir(classe)
            if not atributo.startswith("_") and callable(getattr(classe, atributo, None))
        ]
        saida[nome] = sorted(métodos)
    return saida


__all__ = [
    "PAPEIS_DE_ATOR",
    "SERVICOS",
    "ErroDeContrato",
    "ErroDeExecucao",
    "capacidades",
    "executar",
    "pasta_de_relatorios",
    "servico",
]
