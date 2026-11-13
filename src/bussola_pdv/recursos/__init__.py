"""Imagens da identidade visual do programa (empacotadas junto do código).

Por que estão dentro do pacote, e não em `docs/` ou na raiz:

* o executável do Windows carrega os arquivos por caminho relativo ao pacote
  (ver `empacotamento/bussola.spec`) — se ficassem fora, o `.exe` abriria sem
  logo;
* a interface não depende de rede nem de arquivo do usuário para desenhar a
  marca oficial.

Arquivos:

``logo_mini.png``
    Bússola com o "B" (450×450, fundo transparente, tinta única). É o ícone do
    programa (`.ico`) e o símbolo do menu lateral.
``logo_comercial.png``
    Assinatura horizontal "Bussola PDV · sua loja sempre no rumo certo"
    (296×132, fundo transparente). Aparece no login, no primeiro uso e na área
    administrativa.

Os dois são monocromáticos (azul-marinho) com alfa: por isso a interface pode
tingi-los com a cor da paleta sem perder desenho — ver `ui/identidade.py`.
"""
