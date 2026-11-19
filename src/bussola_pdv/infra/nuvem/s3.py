"""Cliente S3 (AWS e S3-compatível) escrito em biblioteca padrão.

Um backup é `PUT` de um arquivo; restaurar é `GET`; listar e apagar completam o
contrato. Tudo cabe em `http.client` + a assinatura SigV4 de
`bussola_pdv.infra.nuvem.assinatura` — sem `boto3`.

`endpoint` na configuração existe por dois motivos: usar MinIO/Wasabi/R2 (que são
S3-compatíveis) e permitir que o teste aponte para um servidor local de mentira, sem
chamar a AWS de verdade. Com `endpoint` a URL vira *path-style*
(`https://servidor/balde/chave`); sem ele, *virtual-hosted*
(`https://balde.s3.região.amazonaws.com/chave`).
"""

# ruff: noqa: S310 — a URL é montada neste módulo (endpoint + recipiente + chave);
# nenhum endereço vem do usuário como esquema livre, e `file:` não serve a Requisição.


from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from http.client import HTTPResponse
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from . import ConfiguracaoNuvem, ErroNuvem, NuvemNaoConfigurada
from .assinatura import assinar_sigv4

_ENV_ACESSO = "BUSSOLA_AWS_ACCESS_KEY_ID"
_ENV_SECRETA = "BUSSOLA_AWS_SECRET_ACCESS_KEY"
_ENV_SESSAO = "BUSSOLA_AWS_SESSION_TOKEN"


class ArmazenamentoS3:
    """Três operações de backup sobre um balde S3."""

    def __init__(self, configuracao: ConfiguracaoNuvem, *, ambiente: dict[str, str] | None = None):
        import os

        ambiente = ambiente if ambiente is not None else dict(os.environ)
        self.configuracao = configuracao
        self.regiao = configuracao.regiao or "us-east-1"
        self.chave_acesso = ambiente.get(configuracao.variavel_acesso or _ENV_ACESSO, "").strip()
        self.chave_secreta = ambiente.get(configuracao.variavel_chave or _ENV_SECRETA, "").strip()
        self.token_sessao = ambiente.get(_ENV_SESSAO, "").strip()
        if not self.chave_acesso or not self.chave_secreta:
            raise NuvemNaoConfigurada(
                "S3 sem credencial: defina "
                f"{configuracao.variavel_acesso or _ENV_ACESSO} e "
                f"{configuracao.variavel_chave or _ENV_SECRETA} nas variáveis de ambiente "
                "da máquina (docs/NUVEM.md, seção AWS)."
            )

    # -- endereço -----------------------------------------------------------
    def _destino(self, chave: str = "") -> tuple[str, str, str]:
        """(url, host, caminho) da requisição para `chave` (vazio = o balde)."""
        balde = self.configuracao.recipiente
        chave = chave.strip("/")
        if self.configuracao.endpoint:
            partes = urlsplit(self.configuracao.endpoint)
            base = f"{partes.scheme}://{partes.netloc}{partes.path.rstrip('/')}"
            host = partes.netloc
            caminho = f"/{balde}" + (f"/{quote(chave)}" if chave else "")
            return base + caminho, host, caminho
        host = f"{balde}.s3.{self.regiao}.amazonaws.com"
        caminho = "/" + quote(chave) if chave else "/"
        return f"https://{host}{caminho}", host, caminho

    # -- transporte ---------------------------------------------------------
    def _pedir(
        self,
        metodo: str,
        *,
        chave: str = "",
        consulta: dict[str, str] | None = None,
        corpo: bytes | None = None,
        content_type: str = "",
    ) -> tuple[int, bytes]:
        url, host, caminho = self._destino(chave)
        if consulta:
            url += "?" + "&".join(f"{k}={quote(v)}" for k, v in consulta.items())
        cabecalhos_assinados = {"host": host}
        if content_type:
            cabecalhos_assinados["content-type"] = content_type
        if self.configuracao.criptografia and metodo.upper() == "PUT":
            cabecalhos_assinados["x-amz-server-side-encryption"] = self.configuracao.criptografia
        assinados = assinar_sigv4(
            metodo=metodo,
            host=host,
            caminho=caminho,
            consulta=consulta or {},
            regiao=self.regiao,
            servico="s3",
            chave_acesso=self.chave_acesso,
            chave_secreta=self.chave_secreta,
            momento=datetime.now(UTC),
            corpo=corpo or b"",
            cabecalhos=cabecalhos_assinados,
            token_sessao=self.token_sessao,
        )
        enviar = dict(assinados)
        enviar.update(cabecalhos_assinados)
        requisicao = Request(url, data=corpo, method=metodo, headers=enviar)
        try:
            # A URL é montada aqui (endpoint + balde + chave), nunca vem do usuário
            # como esquema arbitrário: `file:` não é aceito pelo urlopen de requisição.
            with urlopen(requisicao, timeout=30) as resposta:
                return resposta.status, resposta.read()
        except HTTPError as exc:
            detalhe = exc.read().decode("utf-8", "replace")[:400]
            raise ErroNuvem(
                f"S3 respondeu {exc.code} em {metodo} {caminho}: {detalhe or exc.reason}"
            ) from exc
        except URLError as exc:
            raise ErroNuvem(f"Sem resposta do S3 ({exc.reason}). Verifique a rede.") from exc

    # -- contrato -----------------------------------------------------------
    def enviar(self, caminho: Path, *, nome: str | None = None) -> str:
        caminho = Path(caminho)
        if not caminho.is_file():
            raise ErroNuvem(f"Arquivo inexistente: {caminho}")
        chave = self.configuracao.prefixo + (nome or caminho.name)
        self._pedir("PUT", chave=chave, corpo=caminho.read_bytes(), content_type=_tipo(caminho))
        return chave

    def baixar(self, nome: str, destino: Path) -> Path:
        _, corpo = self._pedir("GET", chave=nome)
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(corpo)
        return destino

    def listar(self) -> list[str]:
        _, corpo = self._pedir(
            "GET", consulta={"list-type": "2", "prefix": self.configuracao.prefixo}
        )
        raiz = _xml(corpo)
        return [elemento.text or "" for elemento in raiz.iter() if _tag(elemento, "Key")]

    def remover(self, nome: str) -> None:
        self._pedir("DELETE", chave=nome)

    # -- conveniência -------------------------------------------------------
    def existe(self, nome: str) -> bool:
        try:
            self._pedir("HEAD", chave=nome)
        except ErroNuvem:
            return False
        return True


def _tag(elemento: ET.Element, nome: str) -> bool:
    return elemento.tag.rsplit("}", 1)[-1] == nome


def _xml(corpo: bytes) -> ET.Element:
    try:
        return ET.fromstring(corpo)  # noqa: S314 - resposta do próprio provedor
    except ET.ParseError as exc:
        raise ErroNuvem("Resposta do S3 não é XML válido (listagem recusada).") from exc


def _tipo(caminho: Path) -> str:
    sufixo = caminho.suffix.lower()
    if sufixo in {".db", ".sqlite", ".sqlite3"}:
        return "application/vnd.sqlite3"
    if sufixo == ".json":
        return "application/json"
    if sufixo == ".zip":
        return "application/zip"
    return "application/octet-stream"


def fechar(resposta: HTTPResponse) -> None:  # pragma: no cover - utilitário de teste
    resposta.close()


__all__ = ["ArmazenamentoS3"]
