"""Ponto de entrada da instalação empacotada (menu Iniciar / duplo clique).

O que muda em relação a `bussola ui`: **não há terminal**. A base fica no
diretório de dados do usuário e, quando ela ainda não existe, o programa abre a
tela de primeiro uso em vez de exigir um comando `init` com argumentos.

Qualquer argumento na linha de comando devolve o controle ao CLI — é assim que o
executável serve também de ferramenta (`backup`, `info`, `demo`).
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos:
        from ..cli import main as cli_main

        return cli_main(argumentos)

    from ..caminhos import banco_padrao
    from .app import criar_aplicacao, executar
    from .primeiro_uso import DialogoPrimeiroUso, precisa_de_configuracao

    banco = banco_padrao()
    criar_aplicacao()  # garante o QApplication antes de qualquer diálogo
    if precisa_de_configuracao(banco):
        dialogo = DialogoPrimeiroUso(banco)
        if dialogo.exec() != dialogo.DialogCode.Accepted:
            return 0
    return executar(banco)


if __name__ == "__main__":  # pragma: no cover - execução direta
    sys.exit(main())
