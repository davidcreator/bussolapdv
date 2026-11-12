"""Ponto de entrada da instalação empacotada (menu Iniciar / duplo clique).

O que muda em relação a `bussola ui`: **não há terminal**. A base fica no
diretório de dados do usuário e, quando ela ainda não existe, o programa abre a
tela de primeiro uso em vez de exigir um comando `init` com argumentos.

Qualquer argumento na linha de comando devolve o controle ao CLI — é assim que o
executável serve também de ferramenta (`backup`, `info`, `demo`).

Duas garantias que só existem aqui, porque só aqui não há console:

1. **exceção não tratada vira caixa de diálogo** (`diagnostico.instalar_captura_de_erros`),
   em vez de sumir no `stderr` que ninguém vê;
2. **a pasta de dados é recalculada depois do primeiro uso**, já que o operador pode
   ter escolhido outra unidade naquela tela.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos:
        from ..cli import main as cli_main

        return cli_main(argumentos)

    from ..caminhos import banco_padrao
    from ..diagnostico import instalar_captura_de_erros, mostrar_erro
    from .app import criar_aplicacao, executar
    from .primeiro_uso import DialogoPrimeiroUso, precisa_de_configuracao

    criar_aplicacao()  # garante o QApplication antes de qualquer diálogo
    instalar_captura_de_erros()

    try:
        if precisa_de_configuracao(banco_padrao()):
            dialogo = DialogoPrimeiroUso(banco_padrao())
            if dialogo.exec() != dialogo.DialogCode.Accepted:
                return 0
            # a escolha de pasta pode ter mudado o banco: relê antes de abrir
        return executar(banco_padrao())
    except Exception as exc:  # a tela é a última linha de defesa do app empacotado
        mostrar_erro(exc, contexto="inicialização da interface", titulo="Bússola PDV")
        return 1


if __name__ == "__main__":  # pragma: no cover - execução direta
    sys.exit(main())
