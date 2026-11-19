"""Assinatura das requisições de nuvem, em biblioteca padrão (AWS SigV4 e Azure SharedKey).

Motivo de existir: o programa é distribuído como instalador para Windows e não pode
passar a exigir `boto3` ou `azure-storage-blob` (dependência nova, download no
cliente, versão que quebra). As duas assinaturas são aritmética de hash — HMAC-SHA256
e um canônico de texto — perfeitamente fazíveis com `hmac`, `hashlib` e `base64`.

Cada função é pura: recebe dados, devolve cabeçalhos. Nada de rede aqui, para que o
teste possa comparar com os **exemplos publicados** dos fornecedores
(AWS: `5d672d79…`; Azure: o `StringToSign` do Get Blob) sem tocar na nuvem.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote

ALGORITMO_AWS = "AWS4-HMAC-SHA256"
VERSAO_AZURE = "2021-08-06"


def _hmac(chave: bytes, mensagem: str) -> bytes:
    return hmac.new(chave, mensagem.encode("utf-8"), hashlib.sha256).digest()


def _sha256_hex(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _codificar(valor: str) -> str:
    # `quote` com safe="-_.~" é exatamente o percent-encoding exigido pelo SigV4.
    return quote(valor, safe="-_.~")


def consulta_canonica(consulta: dict[str, str] | list[tuple[str, str]]) -> str:
    """Ordena e codifica a query string como o SigV4 espera."""
    itens = consulta.items() if isinstance(consulta, dict) else consulta
    pares = sorted((_codificar(str(k)), _codificar(str(v))) for k, v in itens)
    return "&".join(f"{k}={v}" for k, v in pares)


def assinar_sigv4(
    *,
    metodo: str,
    host: str,
    caminho: str = "/",
    consulta: dict[str, str] | list[tuple[str, str]] | None = None,
    regiao: str,
    servico: str,
    chave_acesso: str,
    chave_secreta: str,
    momento: datetime | None = None,
    corpo: bytes = b"",
    cabecalhos: dict[str, str] | None = None,
    token_sessao: str = "",
    assinar_hash_corpo: bool = True,
) -> dict[str, str]:
    """Devolve os cabeçalhos que autenticam a requisição na AWS (Signature V4).

    `cabecalhos` são os cabeçalhos que farão parte da assinatura além de `host` e
    `x-amz-date` (ex.: `content-type`, `x-amz-content-sha256`). O corpo entra como
    hash; nenhuma credencial é enviada, só a assinatura.
    """
    momento = momento or datetime.now(UTC)
    data = momento.strftime("%Y%m%d")
    carimbo = momento.strftime("%Y%m%dT%H%M%SZ")
    hash_corpo = _sha256_hex(corpo)

    para_assinar: dict[str, str] = {k.lower(): v.strip() for k, v in (cabecalhos or {}).items()}
    para_assinar.setdefault("host", host)
    para_assinar.setdefault("x-amz-date", carimbo)
    if assinar_hash_corpo:
        # O S3 exige o hash do corpo; serviços que não assinam esse cabeçalho
        # (ex.: a API IAM do exemplo publicado) passam `assinar_hash_corpo=False`.
        para_assinar.setdefault("x-amz-content-sha256", hash_corpo)
    if token_sessao:
        para_assinar["x-amz-security-token"] = token_sessao

    nomes = ";".join(sorted(para_assinar))
    canonico_cabecalhos = "".join(f"{nome}:{para_assinar[nome]}\n" for nome in sorted(para_assinar))
    requisicao_canonica = "\n".join(
        [
            metodo.upper(),
            caminho or "/",
            consulta_canonica(consulta or {}),
            canonico_cabecalhos,
            nomes,
            hash_corpo,
        ]
    )
    escopo = f"{data}/{regiao}/{servico}/aws4_request"
    para_assinar_final = "\n".join(
        [ALGORITMO_AWS, carimbo, escopo, _sha256_hex(requisicao_canonica.encode("utf-8"))]
    )
    chave_data = _hmac(("AWS4" + chave_secreta).encode("utf-8"), data)
    chave_regiao = _hmac(chave_data, regiao)
    chave_servico = _hmac(chave_regiao, servico)
    chave_assinatura = _hmac(chave_servico, "aws4_request")
    assinatura = hmac.new(
        chave_assinatura, para_assinar_final.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    cabecalhos_saida = {
        "x-amz-date": carimbo,
        "x-amz-content-sha256": hash_corpo,
        "Authorization": (
            f"{ALGORITMO_AWS} Credential={chave_acesso}/{escopo}, "
            f"SignedHeaders={nomes}, Signature={assinatura}"
        ),
    }
    if token_sessao:
        cabecalhos_saida["x-amz-security-token"] = token_sessao
    return cabecalhos_saida


def data_azure(momento: datetime | None = None) -> str:
    """Formato de data que o Azure Storage exige (RFC 1123 em GMT)."""
    momento = (momento or datetime.now(UTC)).astimezone(UTC)
    return momento.strftime("%a, %d %b %Y %H:%M:%S GMT")


def string_para_assinar_azure(
    *,
    metodo: str,
    conta: str,
    caminho: str,
    consulta: dict[str, str] | None = None,
    content_length: int = 0,
    content_type: str = "",
    content_md5: str = "",
    data: str = "",
    cabecalhos_ms: dict[str, str] | None = None,
) -> str:
    """Monta o `StringToSign` do Shared Key (Blob/Queue/File, versão 2009-09-19+).

    Ordem fixa de 12 linhas, depois os cabeçalhos `x-ms-*` canônicos e, por fim, o
    recurso canônico (`/conta/contêiner/blob` + parâmetros de query ordenados).
    """
    cabecalhos = {k.lower(): v.strip() for k, v in (cabecalhos_ms or {}).items()}
    cabecalhos.setdefault("x-ms-date", data or data_azure())
    cabecalhos.setdefault("x-ms-version", VERSAO_AZURE)
    canonicos = "".join(f"{nome}:{cabecalhos[nome]}\n" for nome in sorted(cabecalhos))

    recurso = "/" + conta + caminho
    if consulta:
        recurso += "\n" + "\n".join(
            f"{k.lower()}:{v}" for k, v in sorted(consulta.items(), key=lambda par: par[0].lower())
        )
    comprimento = "" if content_length == 0 else str(content_length)
    return "".join(
        [
            f"{metodo.upper()}\n",
            "\n",  # Content-Encoding
            "\n",  # Content-Language
            f"{comprimento}\n",
            f"{content_md5}\n",
            f"{content_type}\n",
            "\n",  # Date (vazio: usamos x-ms-date)
            "\n",  # If-Modified-Since
            "\n",  # If-Match
            "\n",  # If-None-Match
            "\n",  # If-Unmodified-Since
            "\n",  # Range
            canonicos,
            recurso,
        ]
    )


def assinar_shared_key(
    *,
    conta: str,
    chave_base64: str,
    string_para_assinar: str,
) -> str:
    """Devolve o valor do cabeçalho `Authorization` do Azure Blob."""
    try:
        chave = base64.b64decode(chave_base64)
    except Exception as exc:  # pragma: no cover - mensagem de erro de configuração
        from . import ErroNuvem

        raise ErroNuvem("A chave da conta Azure precisa estar em base64.") from exc
    assinatura = base64.b64encode(_hmac(chave, string_para_assinar)).decode("ascii")
    return f"SharedKey {conta}:{assinatura}"


__all__ = [
    "ALGORITMO_AWS",
    "VERSAO_AZURE",
    "assinar_shared_key",
    "assinar_sigv4",
    "consulta_canonica",
    "data_azure",
    "string_para_assinar_azure",
]
