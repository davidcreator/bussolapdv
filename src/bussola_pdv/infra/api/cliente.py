"""Cliente HTTP do caixa terminal (modo remoto, ADR-036).

Só biblioteca padrão — mesma escolha do servidor (ADR-032/034): instalar o
programa no Windows não pode significar baixar mais um pacote.

O que este cliente garante:

* **confia em um servidor só**: o `ssl` usa o certificado guardado no primeiro
  uso como única raiz aceita. Servidor impostor na rede da loja não completa o
  handshake, mesmo com certificado "assinado";
* **duas identidades separadas**: o token da API diz que *este programa* pode
  falar com o servidor; a sessão diz *qual pessoa* está no balcão. O cliente
  recusa executar qualquer caso de uso sem sessão;
* **erro do servidor vira erro do domínio**: a tela do terminal mostra a mesma
  mensagem que mostraria no modo local, porque o tipo do erro atravessa o fio;
* **tempo limite curto**: rede de loja engasgada não pode congelar o caixa. Quem
  chama decide o que fazer com a falha (a venda vai para a fila local, por
  exemplo — ver `aplicacao/fila_offline.py`).
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...dominio import erros
from ...dominio.usuario import Usuario, UsuarioRemoto
from ..rede import certificado as certificados
from ..rede.configuracao_terminal import (
    ConfiguracaoRemota,
    ErroDeConfiguracao,
    InspecaoDeCertificado,
)
from .contrato import PonteiroDeAutorizacao, codificar, decodificar, tipo_do_retorno
from .executor import SERVICOS

TEMPO_LIMITE_PADRAO = 15.0


class ErroDeComunicacao(erros.ErroBussola):
    """O servidor não respondeu (rede, TLS, tempo esgotado).

    É a única falha que o terminal trata como "pode tentar de novo": erro de
    regra de negócio, não. Herda de `ErroBussola` para que a tela mostre a
    mensagem do mesmo jeito que mostra "estoque insuficiente" — o operador não
    precisa entender de camadas, precisa saber que a rede caiu.
    """

    codigo = "COMUNICACAO"

    def __init__(self, mensagem: str, *, endereco: str = "") -> None:
        super().__init__(mensagem)
        self.endereco = endereco


#: Tipo do servidor -> exceção do domínio, para a tela reagir igual ao modo local.
_EXCECOES: dict[str, type[Exception]] = {
    nome: objeto
    for nome, objeto in vars(erros).items()
    if isinstance(objeto, type) and issubclass(objeto, erros.ErroBussola)
}


@dataclass
class SessaoDoTerminal:
    token: str
    usuario: UsuarioRemoto
    terminal: str = ""
    expira_em: str = ""
    #: Data de negócio do **servidor** — é ela que manda no fechamento, não o
    #: relógio do balcão (que pode estar em outro fuso, ou errado).
    data_negocio: str = ""
    esquema: int = 0


@dataclass
class ClienteAPI:
    """Fala com o servidor em nome de um operador já autenticado."""

    #: Onde ficam `terminal.json` e o certificado confirmado.
    pasta: Path
    configuracao: ConfiguracaoRemota
    tempo_limite: float = TEMPO_LIMITE_PADRAO
    sessao: SessaoDoTerminal | None = None
    ponteiro: PonteiroDeAutorizacao = field(default_factory=PonteiroDeAutorizacao, repr=False)

    # -- transporte ---------------------------------------------------------
    def _abridor(self) -> urllib.request.OpenerDirector:
        """Abre a conexão já com o certificado do servidor como única raiz."""
        if not self.configuracao.seguro:
            return urllib.request.build_opener()
        contexto = self.configuracao.contexto_tls(self.pasta)
        return urllib.request.build_opener(urllib.request.HTTPSHandler(context=contexto))

    def _pedir(self, metodo: str, rota: str, corpo: dict | None = None) -> dict:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None
        cabecalhos = {
            "Authorization": f"Bearer {self.configuracao.token}",
            "Content-Type": "application/json; charset=utf-8",
            "X-Bussola-Terminal": self.configuracao.terminal,
            "Accept": "application/json",
        }
        if self.sessao is not None:
            cabecalhos["X-Bussola-Sessao"] = self.sessao.token
        pedido = urllib.request.Request(  # noqa: S310 - só http(s), e https fora do loopback
            f"{self.configuracao.base}{rota}", data=dados, method=metodo, headers=cabecalhos
        )
        abertura = self._abridor().open(pedido, timeout=self.tempo_limite)
        try:
            with abertura as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - servidor fora do contrato
            raise ErroDeComunicacao(
                "O servidor respondeu algo que não é JSON.", endereco=self.configuracao.endereco
            ) from exc

    def pedir(self, metodo: str, rota: str, corpo: dict | None = None) -> dict:
        """Chamada crua com tradução de erro. Tudo passa por aqui."""
        try:
            return self._pedir(metodo, rota, corpo)
        except urllib.error.HTTPError as exc:
            self._levantar(exc)
            raise  # pragma: no cover - _levantar sempre levanta
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            motivo = getattr(exc, "reason", exc)
            raise ErroDeComunicacao(
                f"Não consegui falar com o servidor em {self.configuracao.endereco}: {motivo}",
                endereco=self.configuracao.endereco,
            ) from exc
        except ssl.SSLError as exc:
            raise ErroDeComunicacao(
                "O certificado apresentado pelo servidor não é o que este caixa confia. "
                "Confira se o servidor foi reinstalado (a impressão digital muda).",
                endereco=self.configuracao.endereco,
            ) from exc

    @staticmethod
    def _levantar(exc: urllib.error.HTTPError) -> None:
        try:
            corpo = json.loads(exc.read().decode("utf-8"))
        except Exception:  # pragma: no cover - corpo não-JSON em erro
            corpo = {}
        mensagem = str(corpo.get("erro") or f"O servidor respondeu {exc.code}.")
        tipo = str(corpo.get("tipo") or "")
        classe = _EXCECOES.get(tipo)
        if classe is not None:
            raise classe(mensagem) from exc
        if exc.code == 401:
            raise erros.CredenciaisInvalidas(mensagem) from exc
        raise erros.ErroValidacao(mensagem) from exc

    # -- sessão -------------------------------------------------------------
    def abrir_sessao(self, login: str, senha: str) -> SessaoDoTerminal:
        resposta = self.pedir("POST", "/sessao", {"login": login, "senha": senha})
        usuario = decodificar(resposta.get("usuario"), Usuario)
        self.sessao = SessaoDoTerminal(
            token=str(resposta.get("token_sessao") or ""),
            usuario=usuario,
            terminal=str(resposta.get("terminal") or self.configuracao.terminal),
            expira_em=str(resposta.get("expira_em") or ""),
            data_negocio=str(resposta.get("data_negocio") or ""),
            esquema=int(resposta.get("esquema") or 0),
        )
        self.ponteiro.limpar()
        return self.sessao

    def encerrar_sessao(self) -> None:
        if self.sessao is not None:
            try:
                self.pedir("DELETE", "/sessao")
            finally:
                self.sessao = None
                self.ponteiro.limpar()

    @property
    def operador(self) -> UsuarioRemoto | None:
        return self.sessao.usuario if self.sessao is not None else None

    # -- autorização (senha do gerente no balcão) ---------------------------
    def autorizar(self, login: str, senha: str, acao: str | None = None) -> UsuarioRemoto:
        """Troca a senha do autorizador por credencial de uso único.

        O servidor confere a senha e devolve a credencial; a senha **não** fica
        guardada no cliente nem viaja de novo. A credencial vale para o próximo
        pedido que a usar.
        """
        resposta = self.pedir(
            "POST", "/autorizacao", {"login": login, "senha": senha, "acao": acao or ""}
        )
        usuario = decodificar(resposta.get("usuario"), Usuario)
        self.ponteiro.guardar(usuario, str(resposta.get("credencial") or ""))
        return usuario

    # -- casos de uso -------------------------------------------------------
    def executar(self, nome_servico: str, nome_metodo: str, argumentos: dict[str, Any]) -> Any:
        if self.sessao is None:
            raise erros.CredenciaisInvalidas(
                "Faça login neste caixa antes de qualquer operação."
            )
        corpo = {
            "servico": nome_servico,
            "metodo": nome_metodo,
            "argumentos": {
                chave: codificar(valor, self.ponteiro) for chave, valor in argumentos.items()
            },
        }
        resposta = self.pedir("POST", "/executar", corpo)
        classe = SERVICOS.get(nome_servico)
        tipo = tipo_do_retorno(classe, nome_metodo) if classe is not None else None
        return decodificar(resposta.get("resultado"), tipo)

    def capacidades(self) -> dict:
        return self.pedir("GET", "/capacidades")

    def arquivo(self, nome: str) -> bytes:
        """Baixa um relatório gerado no servidor (base64 no JSON, sem multipart)."""
        import base64

        resposta = self.pedir("GET", f"/arquivos?nome={urllib.parse.quote(nome)}")
        return base64.b64decode(str(resposta.get("bytes") or ""))


# -- primeiro uso: descobrir e confirmar o certificado ------------------------


def inspecionar_certificado(endereco: str, *, tempo_limite: float = 10.0) -> InspecaoDeCertificado:
    """Abre uma conexão **sem confiar em nada** só para ler o certificado.

    É o passo que o operador vê: o programa mostra a impressão digital e pede
    confirmação contra a que aparece no servidor. Nada é enviado além do
    handshake — nenhum token, nenhuma senha.
    """
    from urllib.parse import urlparse

    alvo = endereco.strip().rstrip("/")
    partes = urlparse(alvo if "://" in alvo else f"https://{alvo}")
    host = partes.hostname or ""
    porta = partes.port or (443 if partes.scheme == "https" else 80)
    if partes.scheme != "https":
        raise ErroDeConfiguracao("O modo remoto exige https:// (TLS). Confira o endereço.")
    if not host:
        raise ErroDeConfiguracao(f"Endereço inválido: {endereco!r}.")
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE  # só para **ler** o certificado; nada trafega
    try:
        # Uma conexão, um dono: o socket embrulhado fecha o TCP por dentro. Fechar
        # os dois (`with` aninhado) fecharia o mesmo descritor duas vezes e podia
        # pegar um fd reaproveitado por outra conexão.
        cru = socket.create_connection((host, porta), timeout=tempo_limite)
    except OSError as exc:
        raise ErroDeComunicacao(f"Não consegui conectar em {host}:{porta}: {exc}") from exc
    try:
        with contexto.wrap_socket(cru, server_hostname=host) as seguro:
            der = seguro.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as exc:
        cru.close()
        raise ErroDeComunicacao(f"Falha no TLS com {host}:{porta}: {exc}") from exc
    if not der:  # pragma: no cover - servidor sem certificado não existe em TLS
        raise ErroDeComunicacao(f"{host}:{porta} não apresentou certificado.")
    return InspecaoDeCertificado(
        digital=certificados.impressao_digital(der),
        der=der,
    )


__all__ = [
    "TEMPO_LIMITE_PADRAO",
    "ClienteAPI",
    "ErroDeComunicacao",
    "SessaoDoTerminal",
    "inspecionar_certificado",
]
