"""Cliente Azure Blob Storage em biblioteca padrão (Shared Key).

Mesmo contrato do S3 (`enviar`, `baixar`, `listar`, `remover`), mesma ausência de
SDK. A diferença está só na assinatura: `SharedKey conta:hash`, com a chave da conta
em base64 vinda de variável de ambiente.
"""

# ruff: noqa: S310 — a URL é montada neste módulo (endpoint + recipiente + chave);
# nenhum endereço vem do usuário como esquema livre, e `file:` não serve a Requisição.


from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from . import ConfiguracaoNuvem, ErroNuvem, NuvemNaoConfigurada
from .assinatura import VERSAO_AZURE, assinar_shared_key, data_azure, string_para_assinar_azure

_ENV_CONTA = "BUSSOLA_AZURE_CONTA"
_ENV_CHAVE = "BUSSOLA_AZURE_CHAVE"


class ArmazenamentoAzureBlob:
    """Backup de um arquivo num contêiner Azure Blob."""

    def __init__(self, configuracao: ConfiguracaoNuvem, *, ambiente: dict[str, str] | None = None):
        import os

        ambiente = ambiente if ambiente is not None else dict(os.environ)
        self.configuracao = configuracao
        self.conta = (configuracao.conta or ambiente.get(_ENV_CONTA, "")).strip()
        self.chave = ambiente.get(configuracao.variavel_chave or _ENV_CHAVE, "").strip()
        if not self.conta or not self.chave:
            raise NuvemNaoConfigurada(
                "Azure sem credencial: defina BUSSOLA_AZURE_CONTA e BUSSOLA_AZURE_CHAVE "
                "(chave da conta em base64) nas variáveis de ambiente da máquina "
                "(docs/NUVEM.md, seção Azure)."
            )

    def _destino(self, nome: str = "") -> tuple[str, str]:
        """(url, caminho do recurso canônico) para `nome` (vazio = o contêiner)."""
        recipiente = self.configuracao.recipiente
        nome = nome.strip("/")
        if self.configuracao.endpoint:
            partes = urlsplit(self.configuracao.endpoint)
            base = f"{partes.scheme}://{partes.netloc}{partes.path.rstrip('/')}"
        else:
            base = f"https://{self.conta}.blob.core.windows.net"
        caminho = f"/{recipiente}" + (f"/{quote(nome)}" if nome else "")
        return base + caminho, caminho

    def _pedir(
        self,
        metodo: str,
        *,
        nome: str = "",
        consulta: dict[str, str] | None = None,
        corpo: bytes | None = None,
        cabecalhos_extra: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        url, caminho = self._destino(nome)
        if consulta:
            url += "?" + "&".join(f"{k}={quote(v)}" for k, v in consulta.items())
        cabecalhos_ms = {
            "x-ms-date": data_azure(datetime.now(UTC)),
            "x-ms-version": VERSAO_AZURE,
        }
        cabecalhos_ms.update(cabecalhos_extra or {})
        string = string_para_assinar_azure(
            metodo=metodo,
            conta=self.conta,
            caminho=caminho,
            consulta=consulta or None,
            content_length=len(corpo or b""),
            content_type=cabecalhos_ms.get("x-ms-blob-content-type", ""),
            cabecalhos_ms=cabecalhos_ms,
        )
        enviar = dict(cabecalhos_ms)
        enviar["Authorization"] = assinar_shared_key(
            conta=self.conta, chave_base64=self.chave, string_para_assinar=string
        )
        if cabecalhos_ms.get("x-ms-blob-content-type"):
            enviar["Content-Type"] = cabecalhos_ms["x-ms-blob-content-type"]
        requisicao = Request(url, data=corpo, method=metodo, headers=enviar)
        try:
            # URL montada aqui (endpoint ou *.blob.core.windows.net), não vem do usuário.
            with urlopen(requisicao, timeout=30) as resposta:
                return resposta.status, resposta.read()
        except HTTPError as exc:
            detalhe = exc.read().decode("utf-8", "replace")[:400]
            raise ErroNuvem(
                f"Azure respondeu {exc.code} em {metodo} {nome or self.configuracao.recipiente}: "
                f"{detalhe or exc.reason}"
            ) from exc
        except URLError as exc:
            raise ErroNuvem(f"Sem resposta do Azure ({exc.reason}). Verifique a rede.") from exc

    # -- contrato -----------------------------------------------------------
    def enviar(self, caminho: Path, *, nome: str | None = None) -> str:
        caminho = Path(caminho)
        if not caminho.is_file():
            raise ErroNuvem(f"Arquivo inexistente: {caminho}")
        chave = self.configuracao.prefixo + (nome or caminho.name)
        self._pedir(
            "PUT",
            nome=chave,
            corpo=caminho.read_bytes(),
            cabecalhos_extra={"x-ms-blob-type": "BlockBlob"},
        )
        return chave

    def baixar(self, nome: str, destino: Path) -> Path:
        _, corpo = self._pedir("GET", nome=nome)
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(corpo)
        return destino

    def listar(self) -> list[str]:
        _, corpo = self._pedir(
            "GET",
            consulta={
                "restype": "container",
                "comp": "list",
                "prefix": self.configuracao.prefixo,
            },
        )
        try:
            raiz = ET.fromstring(corpo)  # noqa: S314 - resposta do próprio provedor
        except ET.ParseError as exc:
            raise ErroNuvem("Resposta do Azure não é XML válido (listagem recusada).") from exc
        return [
            elemento.text or ""
            for elemento in raiz.iter()
            if elemento.tag.rsplit("}", 1)[-1] == "Name"
        ]

    def remover(self, nome: str) -> None:
        self._pedir("DELETE", nome=nome)


__all__ = ["ArmazenamentoAzureBlob"]
