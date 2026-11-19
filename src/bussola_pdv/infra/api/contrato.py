"""Contrato tipado entre o terminal e o servidor (modo remoto, ADR-036).

Por que **tipado** em vez de um DTO por tela: o terminal roda o mesmo código do
servidor (mesmo domínio, mesmos casos de uso). Em vez de inventar um formato
JSON para cada serviço e manter os dois lados em sincronia à mão, o terminal
codifica os argumentos **segundo a assinatura real do método** e o servidor
decodifica com a mesma anotação. Um campo novo no domínio atravessa os dois
lados sem endpoint novo, e o teste que percorre todos os serviços públicos pega
qualquer tipo que o contrato não saiba representar.

Três regras que não se quebram:

1. **`Usuario` nunca atravessa.** O hash de senha fica no servidor. O que viaja
   é o id, para o servidor conferir; ao executar, ele **substitui** qualquer
   `Usuario` recebido pelo usuário da sessão (ou pelo autorizador autenticado no
   próprio pedido). Um terminal comprometido não promove ninguém.
2. **Dinheiro é inteiro.** Centavos e milésimos viajam como `int`; float não
   entra em valor monetário nem aqui.
3. **O contrato é fechado.** Tipo desconhecido levanta `ErroDeContrato` com o
   nome do tipo — falhar alto em vez de mandar string onde se espera objeto.
"""

from __future__ import annotations

import dataclasses
import inspect
import sqlite3
import types
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from ...dominio.usuario import Acao, Perfil, Usuario, UsuarioRemoto
from ...dominio.venda import Carrinho, ItemCarrinho

ROTULO = "__tipo__"


class ErroDeContrato(RuntimeError):
    """O pedido não pode ser representado ou reconstruído com segurança."""


class _ContratoNaoSuportado(ErroDeContrato):
    pass


# -- codificação (Python -> JSON) ---------------------------------------------

#: Campos que nunca saem do servidor, por tipo.
_CAMPOS_PROIBIDOS: dict[type, frozenset[str]] = {
    Usuario: frozenset({"senha_hash"}),
}


def _codificar_carrinho(carrinho: Carrinho) -> dict[str, Any]:
    return {ROTULO: "Carrinho", "itens": [codificar(item) for item in carrinho.itens]}


def _decodificar_carrinho(dado: Any) -> Carrinho:
    mapa = _como_mapa(dado)
    itens = [decodificar(item, ItemCarrinho) for item in _como_lista(mapa.get("itens", []))]
    return Carrinho.de_itens(itens)


#: Tipos que não são `dataclass` e por isso declaram como atravessam o fio.
CODIFICADORES: dict[type, tuple[Any, Any]] = {
    Carrinho: (_codificar_carrinho, _decodificar_carrinho),
}


class PonteiroDeAutorizacao:
    """Liga o `Usuario` que o terminal conhece à credencial que o servidor emitiu.

    O terminal nunca manda senha dentro do argumento de um serviço: quem autoriza
    digita a senha no diálogo, o terminal troca por uma credencial de uso único
    (`POST /v1/autorizacao`) e manda o token. Assim o pedido diz "fulano
    autorizou" sem carregar segredo, e o servidor ainda confere a permissão.
    """

    def __init__(self) -> None:
        self._credenciais: dict[str, str] = {}

    def guardar(self, usuario: UsuarioRemoto, credencial: str) -> None:
        self._credenciais[usuario.id] = credencial

    def credencial(self, usuario: Any) -> str | None:
        return self._credenciais.get(getattr(usuario, "id", ""))

    def esquecer(self, usuario_id: str) -> None:
        self._credenciais.pop(usuario_id, None)

    def limpar(self) -> None:
        self._credenciais.clear()


def codificar(valor: Any, ponteiro: PonteiroDeAutorizacao | None = None) -> Any:
    """Converte um objeto do domínio no que o JSON sabe carregar."""
    if valor is None or isinstance(valor, (bool, int)):
        return valor
    if isinstance(valor, (Usuario, UsuarioRemoto)):
        return _codificar_usuario(valor, ponteiro)
    if isinstance(valor, Enum):  # antes de `str`: StrEnum também é str
        return codificar(valor.value)
    if isinstance(valor, (str, float)):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Path):
        return str(valor)
    if type(valor) in CODIFICADORES:
        return CODIFICADORES[type(valor)][0](valor)
    if isinstance(valor, sqlite3.Row):
        return {chave: codificar(valor[chave]) for chave in valor}
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return _codificar_dataclass(valor, ponteiro)
    if isinstance(valor, Mapping):
        return {str(chave): codificar(item, ponteiro) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [codificar(item, ponteiro) for item in valor]
    if hasattr(valor, "isoformat"):  # pragma: no cover - datas exóticas
        return str(valor.isoformat())
    raise _ContratoNaoSuportado(
        f"O contrato não sabe representar {type(valor).__name__} em JSON."
    )


def _codificar_usuario(
    valor: Usuario | UsuarioRemoto, ponteiro: PonteiroDeAutorizacao | None
) -> dict[str, Any]:
    """Usuário viaja como referência: id + (quando houver) credencial de autorização."""
    dados: dict[str, Any] = {
        ROTULO: "Usuario",
        "id": getattr(valor, "id", ""),
        "login": getattr(valor, "login", ""),
        "nome": getattr(valor, "nome", ""),
        "perfil": codificar(getattr(valor, "perfil", None)),
    }
    credencial = ponteiro.credencial(valor) if ponteiro is not None else None
    if credencial:
        dados["credencial"] = credencial
    return dados


def _codificar_dataclass(valor: Any, ponteiro: PonteiroDeAutorizacao | None = None) -> dict[str, Any]:
    classe = type(valor)
    proibidos = _CAMPOS_PROIBIDOS.get(classe, frozenset())
    dados: dict[str, Any] = {ROTULO: classe.__name__}
    for campo in dataclasses.fields(valor):
        if campo.name in proibidos:
            continue
        dados[campo.name] = codificar(getattr(valor, campo.name), ponteiro)
    return dados


# -- decodificação (JSON -> Python) ------------------------------------------


def decodificar(dado: Any, tipo: Any) -> Any:
    """Reconstrói `dado` como `tipo`, usando as anotações do próprio domínio."""
    if tipo is None or tipo is Any or tipo is object:
        return dado
    if isinstance(tipo, str):  # anotação não resolvida: devolve cru
        return dado

    origem = get_origin(tipo)
    if origem in (Union, types.UnionType):
        membros = [membro for membro in get_args(tipo) if membro is not type(None)]
        if dado is None:
            return None
        if len(membros) != 1:
            for membro in membros:
                try:
                    return decodificar(dado, membro)
                except (ErroDeContrato, TypeError, ValueError):
                    continue
            raise ErroDeContrato(f"Nenhum tipo de {tipo} aceita o valor recebido.")
        tipo = membros[0]
        origem = get_origin(tipo)

    if origem in (list, set, frozenset, Sequence):
        (interno,) = get_args(tipo) or (Any,)
        itens = [decodificar(item, interno) for item in _como_lista(dado)]
        if origem is set:
            return set(itens)
        if origem is frozenset:
            return frozenset(itens)
        return itens
    if origem is tuple:
        argumentos = get_args(tipo)
        if not argumentos or argumentos == ((),):
            return tuple(_como_lista(dado))
        if len(argumentos) == 2 and argumentos[1] is Ellipsis:
            return tuple(decodificar(item, argumentos[0]) for item in _como_lista(dado))
        return tuple(
            decodificar(item, argumento)
            for item, argumento in zip(_como_lista(dado), argumentos, strict=False)
        )
    if origem is dict:
        chave, valor = get_args(tipo) or (str, Any)
        return {
            decodificar(nome, chave): decodificar(item, valor)
            for nome, item in _como_mapa(dado).items()
        }

    if tipo is bool:
        return bool(dado)
    if tipo is int:
        return int(dado)
    if tipo is float:
        return float(dado)
    if tipo is str:
        return "" if dado is None else str(dado)
    if tipo is Decimal:
        return Decimal(str(dado))
    if tipo is datetime:
        return datetime.fromisoformat(str(dado))
    if tipo is date:
        return date.fromisoformat(str(dado))
    if tipo is Path:
        return Path(str(dado))
    if tipo is Usuario:
        return _decodificar_usuario(dado)
    if isinstance(tipo, type) and issubclass(tipo, Enum):
        return tipo(dado)
    if tipo in CODIFICADORES:
        return CODIFICADORES[tipo][1](dado)
    if dataclasses.is_dataclass(tipo) and isinstance(tipo, type):
        return _decodificar_dataclass(dado, tipo)
    return dado


def _decodificar_usuario(dado: Any) -> UsuarioRemoto:
    if isinstance(dado, UsuarioRemoto):
        return dado
    mapa = _como_mapa(dado)
    concedidas = mapa.get("permissoes_concedidas")
    return UsuarioRemoto(
        login=str(mapa.get("login", "")),
        nome=str(mapa.get("nome", "")),
        perfil=Perfil(mapa.get("perfil", Perfil.ATENDENTE.value)),
        id=str(mapa.get("id", "")),
        ativo=bool(mapa.get("ativo", True)),
        permissoes_concedidas=(
            frozenset(Acao(nome) for nome in concedidas) if concedidas is not None else None
        ),
        credencial=str(mapa.get("credencial", "") or ""),
    )


def _decodificar_dataclass(dado: Any, tipo: type) -> Any:
    if isinstance(dado, tipo):
        return dado
    if not isinstance(dado, Mapping):
        raise ErroDeContrato(f"{tipo.__name__} precisa de um objeto JSON, veio {type(dado).__name__}.")
    rotulo = dado.get(ROTULO)
    if rotulo is not None and rotulo != tipo.__name__:
        raise ErroDeContrato(f"Esperava {tipo.__name__}, recebi {rotulo}.")
    anotacoes = _anotacoes(tipo)
    valores: dict[str, Any] = {}
    for campo in dataclasses.fields(tipo):
        if campo.name not in dado:
            if campo.default is dataclasses.MISSING and campo.default_factory is dataclasses.MISSING:
                raise ErroDeContrato(f"Falta o campo {tipo.__name__}.{campo.name}.")
            continue
        valores[campo.name] = decodificar(dado[campo.name], anotacoes.get(campo.name))
    return tipo(**valores)


_CACHE_ANOTACOES: dict[type, dict[str, Any]] = {}


def _anotacoes(classe: type) -> dict[str, Any]:
    if classe not in _CACHE_ANOTACOES:
        try:
            _CACHE_ANOTACOES[classe] = get_type_hints(classe)
        except Exception:  # pragma: no cover - anotação exótica
            _CACHE_ANOTACOES[classe] = {}
    return _CACHE_ANOTACOES[classe]


def _como_lista(dado: Any) -> list[Any]:
    if isinstance(dado, (list, tuple, set, frozenset)):
        return list(dado)
    raise ErroDeContrato(f"Esperava uma lista, recebi {type(dado).__name__}.")


def _como_mapa(dado: Any) -> Mapping[str, Any]:
    if isinstance(dado, Mapping):
        return dado
    raise ErroDeContrato(f"Esperava um objeto, recebi {type(dado).__name__}.")


# -- assinatura: uma verdade para os dois lados -------------------------------


def assinatura(método: Any) -> inspect.Signature:
    return inspect.signature(método)


def assinatura_remota(classe: type, nome: str) -> inspect.Signature:
    """Assinatura do método **sem** `self` — é o que o terminal enxerga."""
    assinatura_completa = inspect.signature(getattr(classe, nome))
    parametros = list(assinatura_completa.parameters.values())
    if parametros and parametros[0].name == "self":
        parametros = parametros[1:]
    return assinatura_completa.replace(parameters=parametros)


def parametros_remotos(classe: type, nome: str) -> list[inspect.Parameter]:
    """Parâmetros que o terminal precisa mandar (o resto o servidor resolve)."""
    método = getattr(classe, nome)
    anotacoes = _resolver(classe, nome)
    saida: list[inspect.Parameter] = []
    for parametro in assinatura(método).parameters.values():
        tipo = anotacoes.get(parametro.name)
        if parametro.kind in (parametro.VAR_POSITIONAL, parametro.VAR_KEYWORD):
            continue
        if tipo is Usuario:
            continue
        if parametro.name == "autorizador":
            continue
        saida.append(parametro)
    return saida


_CACHE_ASSINATURAS: dict[tuple[type, str], dict[str, Any]] = {}


def _resolver(classe: type, nome: str) -> dict[str, Any]:
    chave = (classe, nome)
    if chave not in _CACHE_ASSINATURAS:
        try:
            _CACHE_ASSINATURAS[chave] = get_type_hints(getattr(classe, nome))
        except Exception:  # pragma: no cover - anotação exótica
            _CACHE_ASSINATURAS[chave] = {}
    return _CACHE_ASSINATURAS[chave]


def tipo_do_retorno(classe: type, nome: str) -> Any:
    return _resolver(classe, nome).get("return")


__all__ = [
    "ROTULO",
    "ErroDeContrato",
    "PonteiroDeAutorizacao",
    "assinatura_remota",
    "codificar",
    "decodificar",
    "parametros_remotos",
    "tipo_do_retorno",
]
