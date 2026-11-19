"""Estruturas de futuro: nuvem (AWS/Azure) e emissão fiscal.

O que se prova aqui é que a **base** existe e que ela **recusa com mensagem útil**
em vez de fingir que funciona: nuvem sem SDK instalado não perde backup em
silêncio, e emissor fiscal desligado não devolve documento nenhum. Também se prova
que o contrato de armazenamento serve para backup de verdade (com um dublê em
memória), para que a implementação do provedor, quando vier, não precise mudar
quem chama.
"""

from __future__ import annotations

import pytest

from bussola_pdv.aplicacao.fiscal import (
    AVISO_FISCAL,
    ConfiguracaoFiscal,
    EmissorFiscalDesativado,
    FiscalIndisponivel,
    emissor_fiscal,
)
from bussola_pdv.infra.nuvem import (
    PROVEDORES,
    REQUISITOS,
    ArmazenamentoAzureBlob,
    ArmazenamentoMemoria,
    ArmazenamentoS3,
    ConfiguracaoNuvem,
    ErroNuvem,
    NuvemNaoConfigurada,
    criar_armazenamento,
    enviar_backup,
)


class TestNuvem:
    def test_contrato_serve_para_backup(self, tmp_path):
        origem = tmp_path / "backup.db"
        origem.write_bytes(b"conteudo-da-base")
        armazenamento = ArmazenamentoMemoria()
        chave = enviar_backup(armazenamento, origem)
        assert chave.endswith("backup.db")
        assert armazenamento.listar() == [chave]

        destino = tmp_path / "restaurado.db"
        armazenamento.baixar(chave, destino)
        assert destino.read_bytes() == origem.read_bytes()

        armazenamento.remover(chave)
        assert armazenamento.listar() == []

    def test_s3_e_azure_existem_mas_nao_estao_configurados(self):
        for classe in (ArmazenamentoS3, ArmazenamentoAzureBlob):
            servico = classe(ConfiguracaoNuvem(provedor="S3", recipiente="bazar"))
            with pytest.raises(NuvemNaoConfigurada, match=r"docs/NUVEM\.md"):
                servico.listar()

    def test_fabrica_escolhe_o_provedor(self):
        assert isinstance(
            criar_armazenamento(ConfiguracaoNuvem(provedor="S3", recipiente="b")),
            ArmazenamentoS3,
        )
        assert isinstance(
            criar_armazenamento(ConfiguracaoNuvem(provedor="AZURE_BLOB", recipiente="c")),
            ArmazenamentoAzureBlob,
        )

    def test_provedor_desconhecido_e_recusado(self):
        with pytest.raises(ErroNuvem, match="Provedor desconhecido"):
            ConfiguracaoNuvem(provedor="GCP", recipiente="b")

    def test_recipiente_obrigatorio(self):
        with pytest.raises(ErroNuvem, match="balde"):
            ConfiguracaoNuvem(provedor="S3", recipiente="  ")

    def test_requisitos_estao_documentados(self):
        chaves = {chave for chave, _ in REQUISITOS}
        assert {"Credencial", "Criptografia", "LGPD"} <= chaves
        assert set(PROVEDORES) == {"S3", "AZURE_BLOB"}

    def test_backup_inexistente_e_recusado(self, tmp_path):
        with pytest.raises(ErroNuvem, match="inexistente"):
            enviar_backup(ArmazenamentoMemoria(), tmp_path / "nao-existe.db")


class TestFiscal:
    def test_emissor_padrao_recusa_emitir_e_explica(self, cenario):
        emissor = emissor_fiscal(cenario.ctx)
        with pytest.raises(FiscalIndisponivel) as erro:
            emissor.emitir("venda-1")
        mensagem = str(erro.value)
        assert "docs/FISCAL.md" in mensagem
        assert "ADR-029" in mensagem

    def test_recusa_tambem_cancelar_e_consultar(self):
        emissor = EmissorFiscalDesativado()
        with pytest.raises(FiscalIndisponivel):
            emissor.cancelar("chave", "motivo")
        with pytest.raises(FiscalIndisponivel):
            emissor.consultar("chave")

    def test_pendencias_listam_o_que_falta(self):
        pendencias = ConfiguracaoFiscal().pendencias()
        texto = " ".join(pendencias)
        assert "CNPJ" in texto
        assert "Certificado" in texto
        assert "UF" in texto

    def test_configuracao_completa_ainda_assim_nao_emite(self):
        configuracao = ConfiguracaoFiscal(
            habilitado=True,
            ambiente="PRODUCAO",
            uf="SP",
            cnpj="12.345.678/0001-90",
            certificado_caminho="C:/certificados/loja.pfx",
            csc_id="1",
            csc_disponivel=True,
        )
        assert configuracao.pendencias() == ()
        with pytest.raises(FiscalIndisponivel):
            EmissorFiscalDesativado(configuracao).emitir("venda-1")

    def test_aviso_de_controle_interno_continua(self):
        assert "não é documento fiscal" in AVISO_FISCAL
