#!/usr/bin/env python3
"""Gera o QR Code do PIX (BR Code / EMV) para a página de doações do repositório.

Por que isto existe: o documento de doação precisa de um QR de verdade, e QR de
"exemplo" é pior do que QR nenhum — quem escaneia um código inventado recebe erro
no aplicativo do banco e desiste. Então o repositório guarda **o gerador**, não uma
imagem de enfeite: quem mantém o projeto roda um comando com a própria chave e o
arquivo é produzido aqui, localmente, sem serviço de terceiros ver a chave.

O que é montado é o **BR Code** do Banco Central (padrão EMV® QRCPS MPM):

===== =========================================================================
Campo Conteúdo
===== =========================================================================
00    `01` (indicador de formato)
26    conta do recebedor: `br.gov.bcb.pix` + chave (+ descrição opcional)
52    `0000` (categoria do estabelecimento)
53    `986` (BRL)
54    valor, quando informado (doação de valor fixo)
58    `BR`
59    nome do recebedor (até 25, sem acento)
60    cidade (até 15, sem acento)
62    dados adicionais (`***` = sem identificador de transação)
63    CRC16-CCITT (FALSE) calculado sobre tudo o que vem antes
===== =========================================================================

Uso::

    # imprime o "copia e cola" e grava o QR em docs/doacoes/qr-pix.svg
    python ferramentas/gerar_qr_pix.py \\
        --chave "https://nubank.com.br/cobrar/gb03d/6af74cfa-7833-49fa-bb52-cf6355464d98" \\
        --nome "DAVID LIMA DE ALMEIDA" \\
        --cidade "SAO PAULO"

    # só conferir o texto, sem escrever arquivo
    python ferramentas/gerar_qr_pix.py --chave ... --nome ... --cidade ... --sem-arquivo

A imagem sai em **SVG** (texto puro, versionável, imprime em qualquer tamanho). Para
PNG, `--formato png` — aí precisa do Pillow, que vem junto com `qrcode[pil]`.

Dependência: `qrcode` (só para desenhar o QR). O "copia e cola" e a validação usam
apenas a biblioteca padrão — `--sem-arquivo` funciona em qualquer Python 3.10+.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

#: Limites do padrão: nome do recebedor 25, cidade 15, descrição 40 (as carteiras
#: costumam aceitar mais na descrição, mas o banco emissor é quem reclama).
MAX_NOME = 25
MAX_CIDADE = 15
MAX_DESCRICAO = 40
MAX_TXID = 25

#: Identificador fixo da conta PIX dentro do payload.
GUI_PIX = "br.gov.bcb.pix"

#: Caminho padrão do QR dentro do repositório.
SAIDA_PADRAO = Path(__file__).resolve().parents[1] / "docs" / "doacoes" / "qr-pix.svg"


# -- montagem do BR Code --------------------------------------------------------
def tlv(identificador: str, valor: str) -> str:
    """Um campo EMV: id (2 dígitos) + tamanho (2 dígitos) + valor."""
    if len(identificador) != 2:
        raise ValueError(f"identificador EMV precisa ter 2 dígitos: {identificador!r}")
    if len(valor) > 99:
        raise ValueError(f"campo {identificador} passou de 99 caracteres ({len(valor)})")
    return f"{identificador}{len(valor):02d}{valor}"


def crc16(texto: str) -> str:
    """CRC16-CCITT (FALSE, polinômio 0x1021, inicial 0xFFFF), em 4 hexadecimais.

    O valor de referência é conhecido: ``crc16("123456789") == "29B1"``. É o que o
    teste usa para não confiar no próprio código.
    """
    crc = 0xFFFF
    for byte in texto.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            # Uma linha só: o desvio do polinômio acontece quando o bit alto está ligado.
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def sem_acento(texto: str) -> str:
    """Nome e cidade vão em ASCII maiúsculo: carteira que recebe "SÃO" reclama."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar_nome(nome: str) -> str:
    limpo = " ".join(sem_acento(nome).split()).upper()
    if not limpo:
        raise ValueError("nome do recebedor é obrigatório")
    return limpo[:MAX_NOME]


def normalizar_cidade(cidade: str) -> str:
    limpa = " ".join(sem_acento(cidade).split()).upper()
    if not limpa:
        raise ValueError("cidade do recebedor é obrigatória")
    return limpa[:MAX_CIDADE]


def normalizar_chave(chave: str) -> str:
    """Limpa e valida a chave PIX (e-mail, telefone, CPF/CNPJ ou aleatória).

    A regra é frouxa de propósito: cada banco aceita um conjunto e o padrão permite
    chave aleatória (EVP) de 32 caracteres. O que não dá para aceitar é chave vazia
    ou com espaço no meio — isso gera um QR que nenhuma carteira lê.
    """
    limpa = chave.strip()
    if not limpa:
        raise ValueError("chave PIX é obrigatória")
    if limpa.startswith("+"):  # telefone E.164: +55DDNNNNNNNNN
        # Aceita a máscara que a pessoa copia do cadastro: +55 (11) 99999-8888.
        digitos = "".join(c for c in limpa if c.isdigit())
        if not 12 <= len(digitos) <= 13:
            raise ValueError(f"telefone deve ser +55 seguido de DDD e número: {limpa!r}")
        return f"+{digitos}"
    if " " in limpa:
        raise ValueError("a chave PIX não pode ter espaço: use a chave, não uma frase")
    if "@" in limpa:  # e-mail: o padrão pede minúsculas
        if "." not in limpa.split("@")[-1]:
            raise ValueError(f"e-mail sem domínio válido: {limpa!r}")
        return limpa.lower()
    if limpa.isdigit():
        if len(limpa) not in (11, 14):
            raise ValueError(
                f"CPF tem 11 dígitos e CNPJ tem 14; recebi {len(limpa)}. "
                "Se for telefone, escreva com +55."
            )
        return limpa
    if 32 <= len(limpa) <= 36:  # EVP (UUID sem hífens ou com)
        return limpa.lower()
    raise ValueError(
        f"chave PIX não reconhecida: {limpa!r}. Aceito e-mail, +55..., CPF (11), "
        "CNPJ (14) ou chave aleatória (32–36 caracteres)."
    )


def normalizar_valor(valor: str | Decimal | int | None) -> str:
    """Valor opcional no formato do padrão: ponto decimal, duas casas, sem milhar."""
    if valor is None or valor == "":
        return ""
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"valor inválido: {valor!r}") from exc
    if numero < 0:
        raise ValueError("valor não pode ser negativo")
    if numero == 0:
        return ""  # zero = deixar a pessoa escolher o valor na hora
    return f"{numero.quantize(Decimal('0.01'))}"


def normalizar_descricao(descricao: str | None) -> str:
    if not descricao:
        return ""
    limpa = " ".join(sem_acento(descricao).split())
    return limpa[:MAX_DESCRICAO]


def normalizar_txid(txid: str | None) -> str:
    """Identificador da transação; ``***`` é o padrão para doação avulsa."""
    if not txid:
        return "***"
    limpo = "".join(c for c in sem_acento(txid) if c.isalnum() or c in "-.*")[:MAX_TXID]
    return limpo or "***"


def montar_payload(
    *,
    chave: str,
    nome: str,
    cidade: str,
    valor: str | Decimal | int | None = None,
    descricao: str | None = None,
    txid: str | None = None,
) -> str:
    """Devolve o BR Code completo, com CRC — o texto do "copia e cola"."""
    conta = tlv("00", GUI_PIX) + tlv("01", normalizar_chave(chave))
    texto_descricao = normalizar_descricao(descricao)
    if texto_descricao:
        conta += tlv("02", texto_descricao)

    partes = [tlv("00", "01"), tlv("26", conta), tlv("52", "0000"), tlv("53", "986")]
    texto_valor = normalizar_valor(valor)
    if texto_valor:
        partes.append(tlv("54", texto_valor))
    partes += [
        tlv("58", "BR"),
        tlv("59", normalizar_nome(nome)),
        tlv("60", normalizar_cidade(cidade)),
        tlv("62", tlv("05", normalizar_txid(txid))),
    ]
    corpo = "".join(partes) + "6304"
    return corpo + crc16(corpo)


def ler_payload(payload: str) -> dict[str, str]:
    """Percorre os campos de primeiro nível — usado para conferir o que foi montado."""
    campos: dict[str, str] = {"63": payload[-4:]}
    posicao = 0
    limite = len(payload) - 4  # o CRC fica de fora da varredura
    while posicao < limite:
        identificador = payload[posicao : posicao + 2]
        tamanho = int(payload[posicao + 2 : posicao + 4])
        campos[identificador] = payload[posicao + 4 : posicao + 4 + tamanho]
        posicao += 4 + tamanho
    return campos


def chave_do_payload(payload: str) -> str:
    """Extrai a chave PIX do subcampo 01 dentro do campo 26 (para o resumo na tela)."""
    conta = ler_payload(payload).get("26", "")
    posicao = 0
    while posicao + 4 <= len(conta):
        identificador = conta[posicao : posicao + 2]
        tamanho = int(conta[posicao + 2 : posicao + 4])
        valor = conta[posicao + 4 : posicao + 4 + tamanho]
        if identificador == "01":
            return valor
        posicao += 4 + tamanho
    return "?"


def conferir(payload: str) -> None:
    """Levanta ``ValueError`` se o payload não fecha (CRC ou estrutura)."""
    if len(payload) < 8:
        raise ValueError("payload curto demais")
    corpo, informado = payload[:-4], payload[-4:]
    if crc16(corpo) != informado.upper():
        raise ValueError(f"CRC não confere: calculado {crc16(corpo)}, no payload {informado}")
    campos = ler_payload(payload)
    if not campos.get("26", "").startswith(tlv("00", GUI_PIX)):
        raise ValueError("campo 26 não aponta para br.gov.bcb.pix")
    if campos.get("53") != "986":
        raise ValueError("moeda diferente de BRL (986)")


# -- desenho do QR --------------------------------------------------------------
def gravar_qr(payload: str, destino: Path, *, formato: str | None = None) -> Path:
    """Desenha o QR em ``destino`` (SVG por padrão, PNG com Pillow instalado)."""
    try:
        import qrcode
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "Para desenhar o QR é preciso o pacote 'qrcode':\n"
            "    pip install 'qrcode[pil]'\n"
            "O texto do 'copia e cola' sai sem ele (use --sem-arquivo)."
        ) from exc

    formato = (formato or destino.suffix.lstrip(".") or "svg").lower()
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # QR de PIX suja/prensado
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    destino.parent.mkdir(parents=True, exist_ok=True)
    if formato == "svg":
        # O submódulo `qrcode.image.svg` não é importado pelo pacote raiz.
        from qrcode.image.svg import SvgPathImage

        imagem = qr.make_image(image_factory=SvgPathImage)
        imagem.save(str(destino))
    elif formato == "png":
        imagem = qr.make_image(fill_color="black", back_color="white")
        imagem.save(str(destino))
    else:
        raise ValueError(f"formato não suportado: {formato!r} (use svg ou png)")
    return destino


# -- linha de comando -----------------------------------------------------------
def _argumentos(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gerar_qr_pix",
        description="Gera o QR Code do PIX (BR Code) e o texto do 'copia e cola'.",
    )
    parser.add_argument("--chave", required=True, help="chave PIX: e-mail, +55..., CPF, CNPJ ou EVP")
    parser.add_argument("--nome", required=True, help="nome do recebedor (vai sem acento, maiúsculo)")
    parser.add_argument("--cidade", required=True, help="cidade do recebedor (sem acento)")
    parser.add_argument("--valor", default=None, help="valor fixo, ex.: 10,00 (vazio = quem doa escolhe)")
    parser.add_argument("--descricao", default=None, help="descrição opcional (até 40 caracteres)")
    parser.add_argument("--txid", default=None, help="identificador da transação (padrão: ***)")
    parser.add_argument(
        "--saida",
        default=str(SAIDA_PADRAO),
        help=f"arquivo do QR (padrão: {SAIDA_PADRAO.relative_to(SAIDA_PADRAO.parents[2])})",
    )
    parser.add_argument("--formato", default=None, choices=["svg", "png"], help="formato da imagem")
    parser.add_argument(
        "--sem-arquivo",
        action="store_true",
        help="só imprime o 'copia e cola' e confere o payload (não precisa de 'qrcode')",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = _argumentos(list(sys.argv[1:] if argv is None else argv))
    try:
        payload = montar_payload(
            chave=argumentos.chave,
            nome=argumentos.nome,
            cidade=argumentos.cidade,
            valor=argumentos.valor,
            descricao=argumentos.descricao,
            txid=argumentos.txid,
        )
        conferir(payload)
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    print("PIX copia e cola (confira no aplicativo do banco antes de publicar):")
    print(payload)
    print()
    campos = ler_payload(payload)
    print(f"  recebedor : {campos.get('59', '?')} ({campos.get('60', '?')})")
    print(f"  chave     : {chave_do_payload(payload)}")
    print(f"  valor     : {campos.get('54', 'quem doa escolhe')}")
    print(f"  CRC       : {campos.get('63')} (confere)")

    if argumentos.sem_arquivo:
        return 0

    destino = Path(argumentos.saida).expanduser()
    try:
        caminho = gravar_qr(payload, destino, formato=argumentos.formato)
    except (RuntimeError, ValueError) as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    print(f"\nQR gravado em {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
