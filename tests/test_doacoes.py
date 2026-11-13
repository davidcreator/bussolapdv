"""Documento de doação e gerador do QR do PIX.

Duas coisas precisam ser verdade aqui, e as duas são sobre **dinheiro de terceiro**:

1. **O que está no payload de PIX é válido.** CRC errado ou campo fora do padrão gera
   um QR que o aplicativo do banco recusa. Por isso o teste não confia no próprio
   código: confere o CRC contra o valor de referência conhecido do CCITT-FALSE e
   relê o payload campo por campo.
2. **O documento não inventa dado bancário.** Enquanto os campos estiverem como
   `«PREENCHER»`, ninguém pode doar para uma conta errada — e um teste falha se
   alguém apagar o marcador sem preencher, ou preencher pela metade.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:  # `ferramentas/` não é pacote instalado
    sys.path.insert(0, str(RAIZ))

from ferramentas import gerar_qr_pix as pix  # noqa: E402

DOC = RAIZ / "CONTRIBUINDO.md"
QR = RAIZ / "docs" / "doacoes" / "qr-pix.svg"
FUNDING = RAIZ / ".github" / "FUNDING.yml"
MARCADOR = "«PREENCHER"

CHAVE_EXEMPLO = "doacoes@exemplo.com"
PAYLOAD_EXEMPLO = pix.montar_payload(chave=CHAVE_EXEMPLO, nome="Maria da Silva", cidade="São Paulo")


class TestCrc:
    def test_valor_de_referencia_do_crc16_ccitt_false(self):
        """`"123456789"` → `0x29B1` é o check value publicado do CCITT-FALSE."""
        assert pix.crc16("123456789") == "29B1"

    def test_crc_e_quatro_hexadecimais_maiusculos(self):
        valor = pix.crc16("bussola")
        assert len(valor) == 4
        assert valor == valor.upper()
        int(valor, 16)  # não pode levantar

    def test_payload_traz_o_crc_de_si_mesmo(self):
        corpo, informado = PAYLOAD_EXEMPLO[:-4], PAYLOAD_EXEMPLO[-4:]
        assert pix.crc16(corpo) == informado


class TestPayload:
    def test_campos_obrigatorios_do_bradesco_ao_banco_central(self):
        campos = pix.ler_payload(PAYLOAD_EXEMPLO)
        assert campos["00"] == "01"
        assert campos["26"].startswith("0014br.gov.bcb.pix")
        assert campos["52"] == "0000"
        assert campos["53"] == "986"  # BRL
        assert campos["58"] == "BR"
        assert campos["59"] == "MARIA DA SILVA"
        assert campos["60"] == "SAO PAULO"
        assert campos["62"] == "0503***"  # txid padrão

    def test_conferir_aceita_o_payload_montado(self):
        pix.conferir(PAYLOAD_EXEMPLO)  # não levanta

    def test_conferir_recusa_crc_adulterado(self):
        adulterado = PAYLOAD_EXEMPLO[:-4] + "0000"
        with pytest.raises(ValueError, match="CRC"):
            pix.conferir(adulterado)

    def test_cada_campo_bate_com_o_proprio_tamanho(self):
        # Percorre o payload cru: se um tamanho estiver errado, a conta não fecha.
        corpo = PAYLOAD_EXEMPLO[:-4]
        posicao = 0
        while posicao < len(corpo) - 4:  # o último campo é o "6304"
            tamanho = int(corpo[posicao + 2 : posicao + 4])
            assert corpo[posicao + 4 : posicao + 4 + tamanho]
            posicao += 4 + tamanho
        assert corpo[posicao:] == "6304"

    def test_chave_do_payload_volta_do_campo_26(self):
        assert pix.chave_do_payload(PAYLOAD_EXEMPLO) == CHAVE_EXEMPLO

    def test_valor_fixo_entra_como_campo_54(self):
        com_valor = pix.montar_payload(
            chave=CHAVE_EXEMPLO, nome="Dora", cidade="Jandira", valor="10,50"
        )
        assert pix.ler_payload(com_valor)["54"] == "10.50"
        pix.conferir(com_valor)

    def test_sem_valor_o_campo_54_nao_existe(self):
        assert "54" not in pix.ler_payload(PAYLOAD_EXEMPLO)

    def test_descricao_opcional_vai_para_o_campo_26(self):
        payload = pix.montar_payload(
            chave=CHAVE_EXEMPLO, nome="Dora", cidade="Jandira", descricao="Doação ao Bússola PDV"
        )
        assert "Doacao ao Bussola PDV" in pix.ler_payload(payload)["26"]
        pix.conferir(payload)


class TestNormalizacao:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("  DOACOES@Exemplo.COM  ", "doacoes@exemplo.com"),
            ("+55 (11) 99999-8888", "+5511999998888"),
            ("52998224725", "52998224725"),
            ("11222333000181", "11222333000181"),
            ("123e4567-e12b-12d1-a456-426655440000", "123e4567-e12b-12d1-a456-426655440000"),
        ],
    )
    def test_chaves_aceitas(self, entrada: str, esperado: str):
        assert pix.normalizar_chave(entrada) == esperado

    @pytest.mark.parametrize(
        "entrada",
        [
            "",
            "   ",
            "chave com espaço",
            "10",  # CPF/CNPJ curto
            "123456789012",  # 12 dígitos: nem CPF nem CNPJ
            "email-sem-dominio@",
            "texto que não é chave",
        ],
    )
    def test_chaves_recusadas(self, entrada: str):
        with pytest.raises(ValueError):
            pix.normalizar_chave(entrada)

    def test_nome_e_cidade_saem_sem_acento_e_maiusculos(self):
        assert pix.normalizar_nome("  João   da Silva ") == "JOAO DA SILVA"
        assert pix.normalizar_cidade("São Paulo") == "SAO PAULO"
        assert pix.normalizar_cidade("São José dos Campos") == "SAO JOSE DOS CA"[:15]

    def test_nome_e_cidade_respeitam_o_limite_do_padrao(self):
        assert len(pix.normalizar_nome("a" * 80)) == pix.MAX_NOME
        assert len(pix.normalizar_cidade("b" * 80)) == pix.MAX_CIDADE

    def test_nome_vazio_e_recusado(self):
        with pytest.raises(ValueError):
            pix.normalizar_nome("   ")
        with pytest.raises(ValueError):
            pix.normalizar_cidade(" \t ")

    @pytest.mark.parametrize(("entrada", "esperado"), [("10,50", "10.50"), (10, "10.00"), ("7", "7.00")])
    def test_valor_vira_ponto_com_duas_casas(self, entrada, esperado: str):
        assert pix.normalizar_valor(entrada) == esperado

    def test_valor_zero_ou_vazio_libera_a_escolha(self):
        assert pix.normalizar_valor(None) == ""
        assert pix.normalizar_valor(0) == ""

    def test_valor_negativo_e_recusado(self):
        with pytest.raises(ValueError):
            pix.normalizar_valor("-1,00")

    def test_txid_padrao(self):
        assert pix.normalizar_txid(None) == "***"
        assert pix.normalizar_txid("doacao-1") == "doacao-1"


class TestLinhaDeComando:
    def test_sem_arquivo_imprime_copia_e_cola(self, capsys):
        codigo = pix.main(
            [
                "--chave",
                CHAVE_EXEMPLO,
                "--nome",
                "Maria da Silva",
                "--cidade",
                "São Paulo",
                "--sem-arquivo",
            ]
        )
        assert codigo == 0
        saida = capsys.readouterr().out
        assert "00020126" in saida
        assert CHAVE_EXEMPLO in saida
        assert "CRC       : " in saida
        assert "(confere)" in saida

    def test_chave_invalida_sai_com_erro_explicado(self, capsys):
        codigo = pix.main(
            ["--chave", "chave inválida", "--nome", "X", "--cidade", "Y", "--sem-arquivo"]
        )
        assert codigo == 2
        assert "espaço" in capsys.readouterr().err

    def test_gera_svg_de_verdade(self, tmp_path):
        pytest.importorskip("qrcode")
        destino = tmp_path / "qr.svg"
        caminho = pix.gravar_qr(PAYLOAD_EXEMPLO, destino)
        assert caminho == destino
        texto = destino.read_text(encoding="utf-8")
        assert texto.startswith("<?xml")
        assert "<svg" in texto
        assert "<path" in texto  # os módulos do QR

    def test_formato_desconhecido_e_recusado(self, tmp_path):
        pytest.importorskip("qrcode")
        with pytest.raises(ValueError, match="formato"):
            pix.gravar_qr(PAYLOAD_EXEMPLO, tmp_path / "qr.gif")


class TestDocumento:
    def test_documento_existe_e_tem_as_tres_formas_de_doar(self):
        texto = DOC.read_text(encoding="utf-8")
        assert "## Parte 1 — Contribuir sem dinheiro" in texto
        assert "## Parte 2 — Apoiar financeiramente" in texto
        for secao in ("### PIX", "### Transferência bancária", "### PayPal"):
            assert secao in texto

    def test_campos_de_recebimento_estao_marcados(self):
        texto = DOC.read_text(encoding="utf-8")
        # Pelo menos chave, titular, banco/agência/conta, PayPal e o copia e cola.
        assert texto.count(MARCADOR) >= 12
        assert "«PREENCHER: chave PIX" in texto
        assert "| **Agência** | `«PREENCHER" in texto
        assert "| **E-mail da conta PayPal** | `«PREENCHER" in texto

    def test_documento_avisa_que_sem_preenchimento_nao_se_doa(self):
        texto = DOC.read_text(encoding="utf-8")
        assert "nenhuma doação deve ser enviada" in texto.lower()
        assert "não pode ser inventado" in texto or "deve ser inventado" in texto

    def test_documento_nao_promete_vantagem_nem_suporte(self):
        texto = DOC.read_text(encoding="utf-8")
        assert "não** compra funcionalidade" in texto
        assert "sem contrapartida" in texto
        assert "GPL-2.0-or-later" in texto

    def test_documento_aponta_para_o_gerador_do_qr(self):
        texto = DOC.read_text(encoding="utf-8")
        assert "ferramentas/gerar_qr_pix.py" in texto
        assert "docs/doacoes/qr-pix.svg" in texto

    def test_qr_do_repositorio_e_um_espaco_reservado(self):
        texto = QR.read_text(encoding="utf-8")
        assert "<svg" in texto
        # Deixa escrito, na própria imagem, que não é QR válido.
        assert "ESPAÇO RESERVADO" in texto
        assert "não é um qr code" in texto.lower()

    def test_funding_leva_ao_documento(self):
        texto = FUNDING.read_text(encoding="utf-8")
        assert "CONTRIBUINDO.md" in texto
        assert texto.count("custom:") >= 1
        assert "buy_me_a_coffee" in texto  # modelo pronto, comentado


class TestRepo:
    def test_readme_aponta_para_o_documento_de_contribuicao(self):
        texto = (RAIZ / "README.md").read_text(encoding="utf-8")
        assert "CONTRIBUINDO.md" in texto
