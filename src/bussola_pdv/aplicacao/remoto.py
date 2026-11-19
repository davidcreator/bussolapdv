"""Modo terminal: a mesma tela, com os casos de uso rodando no servidor (ADR-036).

A ideia em uma frase: **a tela não sabe onde o banco está**. Ela pede
`servicos.pdv.finalizar_venda(...)`. No modo local, isso é o serviço de verdade
com a base da própria máquina; no modo terminal, é um proxy que manda o mesmo
pedido ao servidor, que executa **o mesmo serviço** e devolve o resultado no
formato combinado em `infra/api/contrato.py`.

Por que proxy por introspecção, e não um endpoint por tela: com ~60 chamadas na
interface, um endpoint por chamada significaria dois vocabulários para manter em
sincronia — e a divergência apareceria como bug em produção. Aqui a assinatura do
método **é** o contrato: o proxy lê o tipo de cada argumento e o tipo de retorno
da própria classe do serviço.

Três coisas não são proxy, porque acontecem fisicamente no balcão:

* **impressão** — a impressora está no caixa, não no servidor. O documento é
  montado no servidor (tem os dados) e impresso aqui;
* **gravação de relatório** — o servidor gera, o terminal baixa e salva na pasta
  do próprio caixa;
* **login/autorização** — o servidor confere a senha e devolve sessão ou
  credencial; a senha não fica guardada no terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..dominio.erros import ErroValidacao
from ..dominio.relogio import RelogioSistema
from ..dominio.usuario import Acao, UsuarioRemoto
from ..infra.api.cliente import ClienteAPI, ErroDeComunicacao
from ..infra.api.contrato import assinatura_remota, codificar
from ..infra.api.executor import SERVICOS
from .fila_offline import NOME_DO_ARQUIVO as NOME_DA_FILA
from .fila_offline import FilaDeVendas

# -- proxy de serviço ---------------------------------------------------------


class ServicoRemoto:
    """Objeto que se parece com o serviço local e conversa com o servidor."""

    def __init__(self, cliente: ClienteAPI, nome: str) -> None:
        self.cliente = cliente
        self.nome = nome

    def __getattr__(self, metodo: str) -> Any:
        if metodo.startswith("_"):
            raise AttributeError(metodo)
        classe = SERVICOS.get(self.nome)
        if classe is None or not hasattr(classe, metodo):
            raise AttributeError(f"{self.nome}.{metodo} não existe no servidor.")

        def chamar(*args: Any, **kwargs: Any) -> Any:
            return invocar(self.cliente, self.nome, metodo, args, kwargs)

        chamar.__name__ = metodo
        return chamar

    def __repr__(self) -> str:  # pragma: no cover - depuração
        return f"<ServicoRemoto {self.nome} em {self.cliente.configuracao.endereco}>"


def invocar(
    cliente: ClienteAPI,
    nome_servico: str,
    metodo: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """Liga os argumentos posicionais aos nomes reais e manda para o servidor."""
    classe = SERVICOS[nome_servico]
    try:
        ligados = assinatura_remota(classe, metodo).bind(*args, **kwargs)
    except TypeError as exc:
        raise ErroValidacao(f"Chamada inválida a {nome_servico}.{metodo}: {exc}") from exc
    return cliente.executar(nome_servico, metodo, dict(ligados.arguments))


class VendaGuardadaParaEnvio(ErroValidacao):
    """A rede caiu e a venda foi guardada no caixa para reenvio.

    Não é erro de regra: é aviso. A tela mostra que a venda **está guardada**,
    com a chave para conferência, e que o cupom sai quando o servidor aceitar.
    """

    codigo = "VENDA_NA_FILA"

    def __init__(self, mensagem: str, *, chave: str = "", quantidade: int = 0) -> None:
        super().__init__(mensagem, detalhe={"chave": chave, "pendentes": quantidade})
        self.chave = chave
        self.quantidade = quantidade


class ServicoPDVRemoto(ServicoRemoto):
    """PDV do terminal: venda que não chega ao servidor fica na fila local."""

    def __init__(self, cliente: ClienteAPI, fila: FilaDeVendas) -> None:
        super().__init__(cliente, "pdv")
        self.fila = fila

    def finalizar_venda(self, solicitacao: Any, **kwargs: Any) -> Any:
        try:
            return invocar(self.cliente, "pdv", "finalizar_venda", (solicitacao,), kwargs)
        except ErroDeComunicacao as exc:
            operador = self.cliente.operador
            registro = self.fila.enfileirar(
                solicitacao=solicitacao,
                operador_id=getattr(operador, "id", ""),
                operador_login=getattr(operador, "login", ""),
                terminal=self.cliente.configuracao.terminal,
            )
            raise VendaGuardadaParaEnvio(
                "O servidor não respondeu. A venda foi guardada neste caixa e será "
                "enviada quando a rede voltar — o cupom sai depois, pelo número da venda.",
                chave=registro.chave,
                quantidade=self.fila.quantidade(),
            ) from exc


# -- autenticação remota ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResultadoLoginRemoto:
    usuario: UsuarioRemoto
    terminal: str = ""
    expira_em: str = ""
    rehash_aplicado: bool = False


class ServicoAutenticacaoRemoto:
    """Login vira sessão; autorização vira credencial de uso único."""

    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def entrar(self, login: str, senha: str) -> ResultadoLoginRemoto:
        sessao = self.cliente.abrir_sessao(login, senha)
        return ResultadoLoginRemoto(
            usuario=sessao.usuario, terminal=sessao.terminal, expira_em=sessao.expira_em
        )

    def autorizar(self, login: str, senha: str, acao: Acao) -> UsuarioRemoto:
        return self.cliente.autorizar(login, senha, acao.value)

    def verificar_senha_usuario(self, usuario: UsuarioRemoto, senha: str) -> bool:
        """Confere a senha sem abrir sessão nova (usado em "confirmar identidade")."""
        try:
            self.cliente.autorizar(usuario.login, senha)
        except Exception:
            return False
        return True


# -- exportação remota --------------------------------------------------------


class ServicoExportacaoRemoto:
    """Relatórios são montados no servidor; o arquivo é salvo no caixa.

    O servidor precisa registrar o evento (`exportar` audita e exige permissão),
    então ele grava o arquivo na própria pasta de relatórios e o terminal baixa
    uma cópia para a pasta escolhida pelo operador. O que o operador vê é o
    caminho local, como no modo local.
    """

    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def __getattr__(self, metodo: str) -> Any:
        if metodo.startswith("_"):
            raise AttributeError(metodo)
        if metodo.startswith("exportar"):
            return self._exportar(metodo)
        if not hasattr(SERVICOS["exportacao"], metodo):
            raise AttributeError(f"exportacao.{metodo} não existe no servidor.")

        def chamar(*args: Any, **kwargs: Any) -> Any:
            return invocar(self.cliente, "exportacao", metodo, args, kwargs)

        chamar.__name__ = metodo
        return chamar

    def _exportar(self, metodo: str) -> Any:
        def chamar(*args: Any, **kwargs: Any) -> Path:
            ligados = assinatura_remota(SERVICOS["exportacao"], metodo).bind(*args, **kwargs)
            argumentos = dict(ligados.arguments)
            destino = Path(str(argumentos.get("destino", "relatorio.pdf")))
            nome_no_servidor = destino.name
            argumentos["destino"] = Path(nome_no_servidor)
            self.cliente.executar("exportacao", metodo, argumentos)
            conteudo = self.cliente.arquivo(nome_no_servidor)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            return destino

        chamar.__name__ = metodo
        return chamar


# -- impressão remota ---------------------------------------------------------


class ServicoImpressaoRemoto:
    """Documento montado no servidor, papel saindo no caixa."""

    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def __getattr__(self, metodo: str) -> Any:
        if metodo.startswith("_"):
            raise AttributeError(metodo)
        if metodo in {"despachar", "salvar"}:
            return self._local(metodo)
        if not hasattr(SERVICOS["impressao"], metodo):
            raise AttributeError(f"impressao.{metodo} não existe no servidor.")

        def chamar(*args: Any, **kwargs: Any) -> Any:
            return invocar(self.cliente, "impressao", metodo, args, kwargs)

        chamar.__name__ = metodo
        return chamar

    def _local(self, metodo: str) -> Any:
        from .impressao import entregar, salvar_documento

        def despachar(
            documento: Any,
            *,
            ator: Any = None,
            configuracao: Any = None,
            permissao: Acao = Acao.CUPOM_REIMPRIMIR,
        ) -> Any:
            from .impressao import ResultadoImpressao

            if ator is not None:
                ator.exigir(permissao)
            cfg = configuracao or self.configuracao()
            entregar(documento, cfg)
            return ResultadoImpressao(
                titulo=documento.titulo,
                destino=cfg.impressora,
                motor=cfg.motor,
                papel=documento.papel,
                linhas=len(documento.layout()),
                copias=cfg.copias,
            )

        def salvar(documento: Any, pasta: Path, *, formato: str = "pdf") -> Path:
            return salvar_documento(documento, pasta, formato=formato)

        return despachar if metodo == "despachar" else salvar


# -- consultas de tela --------------------------------------------------------


class ConsultasRemotas:
    """Leituras que a tela faz direto no repositório no modo local."""

    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def _pedir(self, metodo: str, **argumentos: Any) -> Any:
        return self.cliente.executar("consultas", metodo, argumentos)

    def listar_caixas(self) -> list[dict[str, str]]:
        return self._pedir("listar_caixas")

    def turno_aberto(self, caixa_id: str) -> Any:
        return self._pedir("turno_aberto", caixa_id=caixa_id)

    def carregar_turno(self, turno_id: str) -> Any:
        return self._pedir("carregar_turno", turno_id=turno_id)

    def movimentos(self, turno_id: str) -> list[Any]:
        return self._pedir("movimentos", turno_id=turno_id)


class ParametrosRemotos:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def _pedir(self, metodo: str, **argumentos: Any) -> Any:
        return self.cliente.executar("consultas", metodo, argumentos)

    def obter(self, chave: str) -> str:
        return self._pedir("parametro", chave=chave)

    def obter_int(self, chave: str) -> int:
        return self._pedir("parametro_int", chave=chave)

    def obter_bool(self, chave: str) -> bool:
        return self._pedir("parametro_bool", chave=chave)

    def por_prefixo(self, prefixo: str) -> dict[str, str]:
        return self._pedir("parametros_por_prefixo", prefixo=prefixo)


class UsuariosConsultaRemota:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def _pedir(self, metodo: str, **argumentos: Any) -> Any:
        return self.cliente.executar("consultas", metodo, argumentos)

    def por_id(self, usuario_id: str) -> UsuarioRemoto:
        return self._pedir("usuario_por_id", usuario_id=usuario_id)

    def por_login(self, login: str) -> UsuarioRemoto:
        return self._pedir("usuario_por_login", login=login)

    def listar(self) -> list[UsuarioRemoto]:
        return self._pedir("usuarios")


class ProdutosRemotos:
    """Busca do PDV e saldos — o que o caixa precisa para vender."""

    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def _pedir(self, metodo: str, **argumentos: Any) -> Any:
        return self.cliente.executar("consultas", metodo, argumentos)

    def listar(
        self,
        *,
        busca: str = "",
        categoria: str = "",
        apenas_ativos: bool = True,
        limite: int = 500,
    ) -> list[Any]:
        return self._pedir(
            "produtos_listar",
            busca=busca,
            categoria=categoria,
            apenas_ativos=apenas_ativos,
            limite=limite,
        )

    def buscar_leitura(self, entrada: str) -> Any:
        return self._pedir("produto_para_leitura", entrada=entrada)

    def por_id(self, produto_id: str) -> Any:
        return self._pedir("produto_por_id", produto_id=produto_id)

    def por_codigo(self, codigo: str) -> Any:
        return self._pedir("produto_por_codigo", codigo=codigo)

    def saldos(self, produtos_ids: list[str] | None = None) -> dict[str, int]:
        return self._pedir("saldos", produtos_ids=produtos_ids)


class ClientesRemotos:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def listar(self, *, busca: str = "", limite: int = 500) -> list[Any]:
        return self.cliente.executar("consultas", "clientes", {"busca": busca, "limite": limite})


class VendasRemotas:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def por_id(self, venda_id: str) -> Any:
        return self.cliente.executar("consultas", "venda_por_id", {"venda_id": venda_id})

    def listar(self, **filtros: Any) -> list[dict]:
        return self.cliente.executar("consultas", "vendas", filtros)


class EntradasRemotas:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def listar(self, *, limite: int = 200) -> list[dict]:
        return self.cliente.executar("consultas", "entradas", {"limite": limite})


class AuditoriaRemota:
    def __init__(self, cliente: ClienteAPI) -> None:
        self.cliente = cliente

    def listar(self, *, limite: int = 200, data_negocio: str | None = None) -> list[Any]:
        return self.cliente.executar(
            "consultas", "auditoria", {"limite": limite, "data_negocio": data_negocio}
        )

    def verificar(self) -> Any:
        return self.cliente.executar("consultas", "auditoria_verificar", {})


# -- contexto e fábrica de serviços ------------------------------------------


class ContextoRemoto:
    """O que a tela usa do `Contexto`, servido pela rede.

    Existe para que as telas continuem escritas como sempre (`self.ctx.agora()`,
    `self.ctx.parametros.obter_int(...)`) sem abrir banco nenhum. O que ele **não**
    tem é `conexao`, `em_transacao` ou repositório completo — quem escreve é o
    servidor.
    """

    def __init__(self, cliente: ClienteAPI, *, caminho: Path | None = None) -> None:
        self.cliente = cliente
        self.caminho = caminho
        self.remoto = True
        self.terminal = cliente.configuracao.terminal
        self.relogio = RelogioSistema()
        self.caixas = ConsultasRemotas(cliente)
        self.parametros = ParametrosRemotos(cliente)
        self.usuarios = UsuariosConsultaRemota(cliente)
        self.produtos = ProdutosRemotos(cliente)
        self.clientes = ClientesRemotos(cliente)
        self.vendas = VendasRemotas(cliente)
        self.entradas = EntradasRemotas(cliente)
        self.auditoria = AuditoriaRemota(cliente)

    def agora(self) -> datetime:
        """Hora local do caixa (o servidor é quem carimba o que grava)."""
        return self.relogio.agora_utc()

    def data_negocio(self) -> str:
        """A data de negócio é a do **servidor**; o relógio do balcão não decide."""
        sessao = self.cliente.sessao
        if sessao is not None and sessao.data_negocio:
            return sessao.data_negocio
        return self.relogio.data_negocio()

    def versao_esquema(self) -> int:
        sessao = self.cliente.sessao
        return sessao.esquema if sessao is not None else 0

    def fechar(self) -> None:
        return None

    def __enter__(self) -> ContextoRemoto:
        return self

    def __exit__(self, *_: object) -> None:
        return None


@dataclass
class Servicos:
    """Fábrica única usada pela interface, nos dois modos.

    As telas pedem `servicos.pdv`, `servicos.caixa` etc. No modo local são os
    serviços de verdade; no modo terminal, proxies. Nenhuma tela precisa saber
    qual dos dois está em uso — e é isso que fez a janela inteira funcionar pela
    rede sem duplicar interface.
    """

    contexto: Any
    cliente: ClienteAPI | None = None

    @property
    def remoto(self) -> bool:
        return self.cliente is not None

    def _servico(self, nome: str) -> Any:
        if self.cliente is None:
            raise ErroValidacao("Serviço local fora do modo terminal.")
        return ServicoRemoto(self.cliente, nome)

    # -- serviços usados pelas telas ---------------------------------------
    @property
    def fila(self) -> FilaDeVendas:
        """Fila local de vendas do caixa (só faz sentido no modo terminal)."""
        if self.cliente is None:
            raise ErroValidacao("A fila de vendas existe apenas no modo terminal.")
        return _fila_de(self.cliente)

    @property
    def pdv(self) -> Any:
        if not self.remoto:
            return _local(self.contexto, "pdv")
        return ServicoPDVRemoto(self.cliente, self.fila)  # type: ignore[arg-type]

    @property
    def caixa(self) -> Any:
        return self._servico("caixa") if self.remoto else _local(self.contexto, "caixa")

    @property
    def crediario(self) -> Any:
        return self._servico("crediario") if self.remoto else _local(self.contexto, "crediario")

    @property
    def clientes(self) -> Any:
        return self._servico("clientes") if self.remoto else _local(self.contexto, "clientes")

    @property
    def estoque(self) -> Any:
        return self._servico("estoque") if self.remoto else _local(self.contexto, "estoque")

    @property
    def devolucao(self) -> Any:
        return self._servico("devolucao") if self.remoto else _local(self.contexto, "devolucao")

    @property
    def relatorios(self) -> Any:
        return self._servico("relatorios") if self.remoto else _local(self.contexto, "relatorios")

    @property
    def usuarios(self) -> Any:
        return self._servico("usuarios") if self.remoto else _local(self.contexto, "usuarios")

    @property
    def permissoes(self) -> Any:
        return self._servico("permissoes") if self.remoto else _local(self.contexto, "permissoes")

    @property
    def parametros(self) -> Any:
        return self._servico("parametros") if self.remoto else _local(self.contexto, "parametros")

    @property
    def marca(self) -> Any:
        return self._servico("marca") if self.remoto else _local(self.contexto, "marca")

    @property
    def administracao(self) -> Any:
        return self._servico("administracao") if self.remoto else _local(self.contexto, "administracao")

    @property
    def backup(self) -> Any:
        return self._servico("backup") if self.remoto else _local(self.contexto, "backup")

    @property
    def autenticacao(self) -> Any:
        if self.remoto:
            return ServicoAutenticacaoRemoto(self.cliente)  # type: ignore[arg-type]
        return _local(self.contexto, "autenticacao")

    @property
    def exportacao(self) -> Any:
        if self.remoto:
            return ServicoExportacaoRemoto(self.cliente)  # type: ignore[arg-type]
        return _local(self.contexto, "exportacao")

    @property
    def impressao(self) -> Any:
        if self.remoto:
            return ServicoImpressaoRemoto(self.cliente)  # type: ignore[arg-type]
        return _local(self.contexto, "impressao")


_INSTANCIAS: dict[tuple[int, str], Any] = {}
_FILAS: dict[str, FilaDeVendas] = {}


def _fila_de(cliente: ClienteAPI) -> FilaDeVendas:
    chave = str(Path(cliente.pasta) / NOME_DA_FILA)
    if chave not in _FILAS:
        _FILAS[chave] = FilaDeVendas(chave)
    return _FILAS[chave]


def _local(contexto: Any, nome: str) -> Any:
    """Instancia (e reaproveita) o serviço local — mesmo objeto que existia antes."""
    chave = (id(contexto), nome)
    if chave not in _INSTANCIAS:
        _INSTANCIAS[chave] = SERVICOS[nome](contexto)
    return _INSTANCIAS[chave]


def servicos_de(contexto: Any, cliente: ClienteAPI | None = None) -> Servicos:
    """Uma chamada para a tela obter o conjunto de serviços do modo em uso."""
    if cliente is None and getattr(contexto, "remoto", False):
        cliente = getattr(contexto, "cliente", None)
    return Servicos(contexto=contexto, cliente=cliente)


__all__ = [
    "AuditoriaRemota",
    "ClienteAPI",
    "ClientesRemotos",
    "ConsultasRemotas",
    "ContextoRemoto",
    "EntradasRemotas",
    "ErroDeComunicacao",
    "ProdutosRemotos",
    "ResultadoLoginRemoto",
    "ServicoAutenticacaoRemoto",
    "ServicoExportacaoRemoto",
    "ServicoImpressaoRemoto",
    "ServicoPDVRemoto",
    "ServicoRemoto",
    "Servicos",
    "VendaGuardadaParaEnvio",
    "VendasRemotas",
    "codificar",
    "invocar",
    "servicos_de",
]
