"""Saídas de impressão: driver do sistema (padrão), ESC/POS cru, texto e PDF.

O domínio (`bussola_pdv.dominio.impressao`) monta o documento como dado; aqui ele
vira papel. Cada módulo é independente e importa Qt só quando usado, para que o
resto da aplicação (e os testes puros) não paguem o custo de carregar a biblioteca:

* `papel` — desenha na grade de colunas e imprime pelo driver ou salva PDF;
* `escpos` — bytes ESC/POS (corte, gaveta, código de barras nativo);
* `impressoras` — lista as instaladas e envia bytes crus à fila;
* `texto` — prévia em texto puro (`.txt` e depuração da transliteração).
"""

from __future__ import annotations

from .escpos import renderizar as renderizar_espos
from .texto import linhas as linhas_em_texto
from .texto import renderizar as renderizar_texto

__all__ = ["linhas_em_texto", "renderizar_espos", "renderizar_texto"]
