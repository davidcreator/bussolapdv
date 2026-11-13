"""CI: relatório de testes vira anotação, e o workflow não pode voltar a ser mudo.

Motivo destes testes: o workflow do Windows ficava vermelho com a única mensagem
*"Process completed with exit code 1"*, sem dizer qual teste quebrou. O antídoto é
o par `--junitxml` + `ferramentas/anotar_falhas.py`; se alguém remover o relatório do
workflow, o CI volta a ficar mudo — e é isso que estes testes impedem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
# `ferramentas/` não é pacote instalado: entra no caminho só para este teste, porque
# `pytest` (console script, como no ci.yml) não põe o diretório atual no sys.path.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from ferramentas.anotar_falhas import ler, main  # noqa: E402

WORKFLOWS = RAIZ / ".github" / "workflows"

JUNIT_COM_FALHA = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" failures="1" errors="0" skipped="1">
    <testcase classname="tests.test_ajuda.TestPainelMentor" name="test_anda" time="0.01">
      <failure message="AssertionError: passo 2 esperado">traceback...</failure>
    </testcase>
    <testcase classname="tests.test_ajuda.TestServico" name="test_gruda" time="0.01"/>
    <testcase classname="tests.test_impressao" name="test_listar" time="0.0">
      <skipped message="sem impressora"/>
    </testcase>
  </testsuite>
</testsuites>
"""


@pytest.fixture
def relatorio(tmp_path: Path) -> Path:
    arquivo = tmp_path / "relatorio-testes.xml"
    arquivo.write_text(JUNIT_COM_FALHA, encoding="utf-8")
    return arquivo


class TestLeitura:
    def test_conta_total_falhas_e_pulados(self, relatorio: Path):
        falhas, erros, total, pulados = ler(relatorio)
        assert total == 3
        assert len(falhas) == 1
        assert erros == []
        assert pulados == 1

    def test_nome_do_teste_inclui_classe_e_funcao(self, relatorio: Path):
        (falhas, *_resto) = ler(relatorio)
        nome, _arquivo, mensagem = falhas[0]
        assert nome == "tests.test_ajuda.TestPainelMentor::test_anda"
        assert "passo 2 esperado" in mensagem


class TestAnotacao:
    def test_falha_vira_anotacao_com_arquivo_e_nome(self, relatorio: Path, capsys):
        assert main(["anotar", str(relatorio)]) == 1
        saida = capsys.readouterr().out
        assert saida.count("::error") == 1
        assert "file=tests/test_ajuda.py" in saida
        assert "TestPainelMentor" in saida
        assert "3 testes, 1 falha(s), 0 erro(s), 1 pulado(s)" in saida

    def test_relatorio_sem_falha_nao_derruba_o_passo(self, tmp_path: Path, capsys):
        limpo = tmp_path / "ok.xml"
        limpo.write_text(
            '<?xml version="1.0"?><testsuites><testsuite tests="1">'
            '<testcase classname="a" name="teste" time="0.0"/></testsuite></testsuites>',
            encoding="utf-8",
        )
        assert main(["anotar", str(limpo)]) == 0
        saida = capsys.readouterr().out
        assert "::error" not in saida
        assert "1 testes, 0 falha(s)" in saida

    def test_relatorio_ausente_avisa_sem_falhar(self, tmp_path: Path, capsys):
        assert main(["anotar", str(tmp_path / "nao_existe.xml")]) == 0
        assert "::warning::" in capsys.readouterr().out

    def test_relatorio_corrompido_avisa_sem_falhar(self, tmp_path: Path, capsys):
        ruim = tmp_path / "ruim.xml"
        ruim.write_text("<nao-e-xml", encoding="utf-8")
        assert main(["anotar", str(ruim)]) == 0
        assert "ilegível" in capsys.readouterr().out


class TestWorkflows:
    """O CI precisa gerar o relatório e chamar o anotador — nos dois sistemas."""

    @pytest.mark.parametrize("nome", ["ci.yml", "windows.yml"])
    def test_workflow_gera_relatorio_e_anota_falhas(self, nome: str):
        texto = (WORKFLOWS / nome).read_text(encoding="utf-8")
        assert "--junitxml=relatorio-testes.xml" in texto
        assert "ferramentas/anotar_falhas.py relatorio-testes.xml" in texto
        assert "if: failure()" in texto
        assert "if: always()" in texto

    def test_windows_roda_a_suite_em_offscreen(self):
        texto = (WORKFLOWS / "windows.yml").read_text(encoding="utf-8")
        # sem offscreen o Qt do Windows tenta abrir janela no runner e a suíte morre
        assert "QT_QPA_PLATFORM: offscreen" in texto
        assert "python -m pytest tests" in texto
