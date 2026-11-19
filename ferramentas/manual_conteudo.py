"""Texto do manual web — capítulos, seções e o que cada uma mostra.

Separado do gerador (`gerar_manual.py`) de propósito: aqui há **texto**, lá há
formatação. Cada seção pode pedir até quatro coisas ao gerador:

* `guia`  — a chave de um tema do guia do programa (o mesmo do `F1`); o gerador
  cola passos, tabela de campos, atalhos e os cuidados daquele tema;
* `imagem` — uma captura de `docs/capturas/` e a legenda (o que olhar nela);
* `demo`   — um dos simuladores interativos do manual;
* `avancado` — um bloco recolhido, para quem já conhece o assunto.

O texto foi escrito para quem nunca usou um PDV: frases curtas, o que fazer na
ordem em que se faz, e o "por que" só depois do "como".
"""

from __future__ import annotations

CAPITULOS: list[dict] = [
    # ------------------------------------------------------------------ 1
    {
        "id": "comecar",
        "titulo": "Começando por aqui",
        "resumo": "O que o programa é, o que ele não é, e como ler este manual.",
        "icone": "🧭",
        "secoes": [
            {
                "id": "oque-e",
                "titulo": "O que é o Bússola PDV",
                "corpo": """
<p>O Bússola é um programa de <strong>ponto de venda</strong> (o caixa da loja) que roda no
computador da própria loja, sem internet. Ele registra a venda, controla o que entrou e o que saiu
do estoque, guarda o cadastro de produtos e clientes, controla o crediário, fecha o caixa do dia e
mantém um histórico de tudo o que foi alterado.</p>
<p>Ele nasceu para o <strong>bazar de uma ONG</strong>: a operação é uma ou duas pessoas no balcão, um
caixa, e a coordenação querendo saber no fim do dia quanto entrou, o que saiu da prateleira e quem
ficou devendo no crediário — no lugar das anotações em caderneta, que ninguém consegue somar nem
conferir depois. Serve igualmente para varejo pequeno: mercearia, loja de bairro, conveniência, loja de
roupa.</p>
<div class="aviso aviso-info"><p class="aviso-titulo">Antes de tudo, a parte honesta</p>
<p>Este programa <strong>não emite documento fiscal</strong> (NF-e, NFC-e, SAT, cupom fiscal) — e isso
é <strong>decisão de escopo, não pendência</strong>: o uso é <strong>interno</strong>, de controle da
própria loja. O cupom que ele imprime diz, no rodapé, que não é documento fiscal, e o mesmo aviso
acompanha todo relatório exportado.</p>
<p>Se a sua loja precisa de nota fiscal, <strong>este não é o sistema</strong>: ele não substitui
contador nem sistema fiscal certificado. Quem precisa de nota continua precisando de um emissor
fiscal.</p></div>
""",
            },
            {
                "id": "faz-nao-faz",
                "titulo": "O que ele faz e o que ele não faz",
                "corpo": """
<div class="duas-colunas">
<div>
<h3>Faz</h3>
<ul>
<li>Vende com código interno ou código de barras, com desconto por item e por venda.</li>
<li>Divide o pagamento em <strong>até três formas</strong> (dinheiro, PIX, débito, crédito, crediário)
e calcula o troco.</li>
<li>Controla <strong>turno de caixa</strong>: abertura com fundo de troco, sangria, suprimento,
conferência de cédulas e fechamento com justificativa de diferença.</li>
<li>Guarda o catálogo de produtos e clientes e o estoque por movimentos (venda, entrada, ajuste),
com ponto de pedido. <strong>O cadastro em si ainda não tem botão na tela</strong> — veja
<a href="#nao-da-pela-tela">o que ainda não dá para fazer só pela tela</a>.</li>
<li>Controla o <strong>crediário</strong>: títulos, parcelas, atraso e recebimento parcial.</li>
<li>Exporta qualquer relatório em <strong>Excel (.xlsx)</strong> e <strong>PDF</strong>.</li>
<li>Imprime em impressora comum (folha A4) e em impressora térmica de bobina 58 mm e 80 mm.</li>
<li>Guarda uma <strong>trilha de auditoria</strong> com encadeamento de hash: ninguém apaga evento
sem que a cadeia quebre e o programa avise.</li>
<li>Faz <strong>cópia de segurança</strong> verificada, uma vez por dia, e sabe restaurar.</li>
</ul>
</div>
<div>
<h3>Não faz, por decisão de escopo</h3>
<ul>
<li><strong>Não emite documento fiscal.</strong> O uso é interno (bazar de ONG, controle no lugar da
caderneta): nota fiscal, homologação com contador e integração com fornecedor fiscal estão fora
desta fase. O cupom e os relatórios avisam, no rodapé, que não são documento fiscal.</li>
<li>Não vende em <strong>vários caixas na mesma base</strong> pela rede. O projeto é de um caixa
por base; multi-caixa é outro projeto (pendência P2).</li>
<li>Não calcula <strong>juros nem encargos</strong> de crediário atrasado (P3).</li>
<li>Não acessa a internet: não tem login em nuvem, não sincroniza, não tem telemetria.</li>
<li>Não importa planilha de produtos (P10) — o cadastro é pela tela.</li>
</ul>
</div>
</div>
""",
            },
            {
                "id": "nao-da-pela-tela",
                "titulo": "O que já tem botão e o que ainda não tem",
                "corpo": """
<p>Antes de o bazar começar a usar, é justo você saber o que já funciona pela tela e o que ainda
depende de alguém com acesso técnico. A lista abaixo foi tirada do próprio programa desta versão.</p>
<div class="tabela-rolagem"><table class="tabela">
<caption>O que a tela faz nesta versão</caption>
<thead><tr><th>O que você quer fazer</th><th>Como está hoje</th></tr></thead>
<tbody>
<tr><th scope="row">Vender, abrir e fechar caixa, cancelar venda</th>
<td><span class="pilula pilula-dica">pela tela</span> módulos PDV, Caixa e Vendas.</td></tr>
<tr><th scope="row">Consultar, exportar (Excel/PDF) e imprimir</th>
<td><span class="pilula pilula-dica">pela tela</span> Produtos, Vendas, Fechamento, Auditoria,
Clientes, Crediário e Estoque.</td></tr>
<tr><th scope="row">Usuários, permissões, parâmetros, marca da loja, backup</th>
<td><span class="pilula pilula-dica">pela tela</span> área Administração.</td></tr>
<tr><th scope="row">Criar ou alterar produto (preço, custo, mínimo)</th>
<td><span class="pilula pilula-atencao">ainda não</span> a tela Produtos consulta, exporta e imprime;
o cadastro entra pelo serviço técnico do programa.</td></tr>
<tr><th scope="row">Criar cliente, com documento e limite</th>
<td><span class="pilula pilula-atencao">ainda não</span> a tela Clientes consulta, exporta e imprime.</td></tr>
<tr><th scope="row">Lançar estoque inicial, entrada de mercadoria ou ajuste</th>
<td><span class="pilula pilula-atencao">ainda não</span> a tela Estoque mostra movimentos e saldos.
O módulo <em>Entradas</em> aparece no menu, mas a página ainda não existe nesta versão.</td></tr>
<tr><th scope="row">Receber parcela do crediário (dar baixa)</th>
<td><span class="pilula pilula-atencao">ainda não</span> a tela Crediário mostra títulos, atraso e
saldo, e exporta — mas a baixa de recebimento ainda não tem botão.</td></tr>
</tbody></table></div>
<div class="aviso aviso-atencao"><p class="aviso-titulo">O que isso significa na prática</p>
<p>Para <strong>operar o dia</strong> — vender, receber, conferir a gaveta, fechar o caixa e exportar o
relatório — o programa está pronto. Para <strong>colocar o catálogo do bazar dentro dele</strong>
(produtos, clientes, saldo inicial) ainda é preciso alguém com acesso ao serviço do programa.
Combine isso com quem cuida do computador da ONG <em>antes</em> do primeiro dia.</p>
<p>Para treinar a equipe sem encostar nos dados reais, peça uma <strong>base de demonstração</strong>
(loja fictícia, usuários de teste, senha <code>Bussola#2026</code>): o comando está no capítulo
<a href="#cli">Linha de comando</a>.</p></div>
""",
            },
            {
                "id": "caderneta-para-sistema",
                "titulo": "Da caderneta para o sistema",
                "corpo": """
<p>O programa não muda o que o bazar faz; muda <strong>onde a informação fica</strong>. A caderneta
continua servindo de rascunho se você quiser, mas ela deixa de ser o único lugar onde o dia existe —
e é isso que resolve o problema de somar tudo à mão no fim do dia.</p>
<div class="tabela-rolagem"><table class="tabela">
<caption>O que muda no dia a dia</caption>
<thead><tr><th>Pergunta do dia</th><th>Com a caderneta</th><th>Com o Bússola</th></tr></thead>
<tbody>
<tr><th scope="row">Quanto vendi hoje?</th>
<td>Somar as linhas do dia, conferir duas vezes.</td>
<td>O fechamento do turno dá o total, com cada venda registrada e o detalhe por forma de pagamento.</td></tr>
<tr><th scope="row">Quem está devendo?</th>
<td>Página do crediário, com rasura e risco de perder o rastro.</td>
<td>Títulos e parcelas, com atraso, tempo de atraso e recebimento parcial ou total.</td></tr>
<tr><th scope="row">Ainda tem na prateleira?</th>
<td>Contar item por item.</td>
<td>Saldo é a soma dos movimentos (venda, entrada, ajuste), com aviso de ruptura e de ponto de pedido.</td></tr>
<tr><th scope="row">Quanto entrou de dinheiro e quanto saiu?</th>
<td>Papel solto para sangria e suprimento, fácil de perder.</td>
<td>Turno de caixa com fundo de troco, sangria, suprimento e diferença que pede justificativa.</td></tr>
<tr><th scope="row">Quem deu esse desconto?</th>
<td>Ninguém lembra.</td>
<td>A autorização é nominal e fica na trilha de auditoria, com data, valor e motivo.</td></tr>
<tr><th scope="row">E se o caderno perder ou molhar?</th>
<td>Perdeu o histórico.</td>
<td>Cópia de segurança verificada, uma vez por dia, com restauração pela própria tela.</td></tr>
<tr><th scope="row">Como presto contas à coordenação?</th>
<td>Refazer as contas e digitar uma planilha.</td>
<td>Fechamento e relatórios exportados em <strong>Excel</strong> e <strong>PDF</strong>, direto da tela.</td></tr>
</tbody></table></div>

<h4>Como fazer a virada sem susto</h4>
<ol class="passos">
<li><strong>Escolha um dia calmo</strong> para começar e faça a contagem inicial do que está na
prateleira — <em>no papel</em>, para não perder o número. Lançar esse saldo no programa ainda não tem
botão: é feito pelo serviço técnico, junto com o cadastro dos produtos (veja
<a href="#nao-da-pela-tela">o que já tem botão e o que ainda não tem</a>).</li>
<li><strong>Cadastre primeiro o que sai toda semana</strong> — o resto entra conforme aparece. Produto
sem cadastro não é vendido, então é isso que trava o balcão no começo.</li>
<li><strong>Rode os dois em paralelo por alguns dias</strong>, se preferir: use o programa para vender
e a caderneta só para o que ele ainda não tem. A comparação de um dia para o outro mostra se algo
ficou de fora.</li>
<li><strong>Feche o turno todos os dias</strong>, mesmo nos dias parados. É o fechamento que substitui
a soma da caderneta — e é ele que a coordenação vai querer ver.</li>
</ol>

<div class="aviso aviso-atencao"><p class="aviso-titulo">As dívidas antigas precisam de uma decisão sua</p>
<p>O programa cria título de crediário a partir de uma <strong>venda a prazo</strong>; não existe
importação da caderneta (é o item "não importa planilha" desta mesma lista). Trazer os saldos em aberto
da caderneta antiga, portanto, é uma decisão de vocês: a forma mais direta é lançar cada dívida como
uma venda a prazo no dia da virada, com o valor devedor. Combine com a coordenação antes e anote o
critério — quem lançou e quando fica registrado na auditoria.</p></div>

<div class="aviso aviso-dica"><p class="aviso-titulo">Ninguém precisa decorar tela</p>
<p>O programa explica a si mesmo: <kbd>F1</kbd> abre o guia da tela em que você está, e o
<strong>mentor</strong> conduz passo a passo quem está começando — ele destaca o campo do próximo
passo. Este manual é para ler com calma e consultar depois; no balcão, o <kbd>F1</kbd> resolve.</p></div>
""",
            },
            {
                "id": "como-ler",
                "titulo": "Como ler este manual",
                "corpo": """
<p>Este manual foi escrito para o <strong>bazar da ONG</strong>: para quem vai passar a manhã no
balcão sem nunca ter usado um caixa, e para a coordenação, que precisa conferir o dia e prestar contas.
Ele está em ordem de uso: instalar, entrar, conhecer a tela, operar o dia, fechar o dia, administrar e,
no fim, o que só interessa a quem entende de computador.</p>
<ul>
<li>Quem vai <strong>operar o caixa</strong> precisa dos capítulos 3 a 18. Os capítulos 1, 2 e 19 a
25 são do responsável pela instalação e da administração.</li>
<li>Cada seção tem <strong>passos numerados</strong>, a <strong>tabela campo por campo</strong> da
tela e os <strong>atalhos de teclado</strong> — o mesmo texto que o programa mostra quando você
aperta <kbd>F1</kbd>.</li>
<li>As capturas de tela são do programa de verdade, em português, com dados fictícios de
demonstração. Clique numa imagem para ampliar.</li>
<li>Onde aparece <span class="marca-avancado">Para usuário avançado</span>, há um bloco recolhido com
comando de terminal, caminho de arquivo ou detalhe de arquitetura. Se você não precisa, ignore: nada
ali é obrigatório.</li>
<li>As caixas coloridas querem dizer: <span class="pilula pilula-dica">Dica</span> atalho que
economiza tempo; <span class="pilula pilula-atencao">Atenção</span> algo que pode dar errado;
<span class="pilula pilula-perigo">Perigo</span> risco de perder dado.</li>
</ul>
""",
            },
            {
                "id": "glossario",
                "titulo": "Glossário rápido",
                "corpo": """
<p>Se alguma palavra deste manual parecer técnica demais, ela provavelmente está aqui.</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Palavra</th><th>O que quer dizer na prática</th></tr></thead>
<tbody>
<tr><th scope="row">Turno</th><td>O período em que um caixa fica aberto, do fundo de troco até o
fechamento. Sem turno aberto o programa não finaliza venda.</td></tr>
<tr><th scope="row">Sangria</th><td>Dinheiro que <em>sai</em> da gaveta durante o turno (levado ao
cofre, ao banco, para pagar um fornecedor).</td></tr>
<tr><th scope="row">Suprimento</th><td>Dinheiro que <em>entra</em> na gaveta além das vendas
(trocando notas miúdas, por exemplo).</td></tr>
<tr><th scope="row">Fundo de troco</th><td>O dinheiro que já está na gaveta quando o turno abre.</td></tr>
<tr><th scope="row">Ponto de pedido</th><td>Quantidade mínima de um produto; abaixo dela o programa
avisa que está na hora de repor.</td></tr>
<tr><th scope="row">Título</th><td>Uma dívida do cliente no crediário, dividida em parcelas.</td></tr>
<tr><th scope="row">Aging</th><td>Classificação das parcelas por atraso (a vencer, 1–30 dias,
31–60…).</td></tr>
<tr><th scope="row">Trilha de auditoria</th><td>Lista de tudo o que aconteceu de sensível, em ordem,
com uma "impressão digital" (hash) que encadeia um evento no outro.</td></tr>
<tr><th scope="row">Backup</th><td>Cópia de segurança da base de dados, em arquivo, com um
manifesto que permite saber se a cópia está íntegra.</td></tr>
<tr><th scope="row">Base de dados</th><td>O arquivo <code>pdv.db</code> onde ficam vendas,
produtos, clientes e tudo o mais.</td></tr>
<tr><th scope="row">Bazar</th><td>O uso para o qual este programa foi feito: a loja da ONG, com
poucas pessoas no balcão e prestação de contas à coordenação.</td></tr>
<tr><th scope="row">Caderneta</th><td>O caderno de papel onde as vendas, as dívidas e as saídas de
dinheiro eram anotadas à mão. O programa existe para tirar o dia de dentro dele.</td></tr>
<tr><th scope="row">Coordenação</th><td>Quem responde pelo bazar: confere o fechamento, olha os
relatórios e decide o que fazer com o dinheiro e com as dívidas.</td></tr>
<tr><th scope="row">Prestação de contas</th><td>Mostrar o que entrou, o que saiu e o que sobrou em um
período. Sai do Fechamento e das telas de relatório em Excel ou PDF.</td></tr>
</tbody></table></div>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 2
    {
        "id": "instalar",
        "titulo": "Instalar o programa",
        "resumo": "Windows (instalador ou portátil), Linux e macOS — do zero.",
        "icone": "💾",
        "secoes": [
            {
                "id": "instalar-windows",
                "titulo": "Windows — o caminho mais simples",
                "corpo": """
<p>São dois caminhos, e nenhum deles pede senha de administrador.</p>
<h3>A. Instalador (.exe)</h3>
<ol class="passos">
<li><strong>Baixe</strong> o arquivo <code>BussolaPDV-&lt;versão&gt;-setup.exe</code>.</li>
<li><strong>Dê duplo clique.</strong> Se o Windows mostrar a tela azul "O Windows protegeu o
computador", clique em <em>Mais informações</em> e depois em <em>Executar assim mesmo</em>. Isso
acontece porque o programa não tem assinatura digital paga — não porque ele faça algo suspeito.</li>
<li><strong>Avançar</strong> na tela de boas-vindas.</li>
<li><strong>Escolha a pasta</strong> onde o programa vai ficar. O padrão é
<code>C:\\Users\\SeuNome\\AppData\\Local\\Programs\\BussolaPDV</code>, mas você pode trocar — inclusive
para outro disco, como <code>D:\\pdv</code>.</li>
<li><strong>Instalar</strong> e, no fim, deixar marcado <em>Abrir o Bússola PDV</em>.</li>
</ol>
<h3>B. Versão portátil (.zip)</h3>
<p>Se você não quer instalar nada: baixe o <code>.zip</code>, clique com o botão direito e escolha
<em>Extrair tudo</em>, e dê duplo clique em <code>BussolaPDV.exe</code> dentro da pasta extraída.
Funciona de pendrive; nada é gravado no registro do Windows.</p>
<div class="aviso aviso-atencao"><p class="aviso-titulo">Onde ficam os dados não é aqui</p>
<p>A pasta que você escolhe na instalação guarda só o <strong>programa</strong>. A base de dados
(<code>pdv.db</code>), as cópias de segurança e os relatórios ficam em
<code>%LOCALAPPDATA%\\BussolaPDV</code> — ou na pasta que você escolher na primeira abertura.
Assim, atualizar ou desinstalar o programa não apaga venda nenhuma.</p></div>
""",
                "avancado": """
<p>Silencioso, para instalar em várias máquinas: <code>BussolaPDV-&lt;versão&gt;-setup.exe /SILENT /DIR="D:\\pdv"</code>.
O instalador é feito com Inno Setup 6; o script é <code>empacotamento/instalador.iss</code>.</p>
""",
            },
            {
                "id": "instalar-linux",
                "titulo": "Linux",
                "corpo": """
<p>O pacote é um arquivo <code>.tar.gz</code> com um instalador de usuário dentro — nada de
<code>sudo</code>, nada de senha de administrador.</p>
<ol class="passos">
<li><strong>Extraia</strong> o pacote inteiro:
<pre><code>tar -xzf BussolaPDV-&lt;versão&gt;-linux-x86_64.tar.gz</code></pre></li>
<li><strong>Entre na pasta</strong> e rode o instalador:
<pre><code>cd BussolaPDV-&lt;versão&gt;-linux-x86_64
./Instalar.sh</code></pre></li>
<li>Pronto: o programa vai para <code>~/.local/opt/bussolapdv</code>, o ícone entra no tema do
usuário e o atalho aparece no menu de aplicativos.</li>
</ol>
<p>Para só experimentar, sem instalar: <code>./Iniciar.sh</code> roda direto da pasta. Para remover o
programa depois: <code>./Instalar.sh --remover</code> (a base de dados fica intacta).</p>
""",
                "avancado": """
<p>Se existir <code>appimagetool</code>, o mesmo comando do projeto gera também um <code>.AppImage</code>
de arquivo único. Detalhes em <code>docs/PACOTES.md</code>.</p>
""",
            },
            {
                "id": "instalar-macos",
                "titulo": "macOS",
                "corpo": """
<ol class="passos">
<li><strong>Descompacte</strong> o <code>.zip</code> (duplo clique) ou abra o <code>.dmg</code>.</li>
<li><strong>Arraste</strong> o <code>BussolaPDV.app</code> para a pasta <em>Aplicativos</em>.</li>
<li>Na primeira abertura, <strong>clique com o botão direito</strong> no aplicativo e escolha
<em>Abrir</em>. O macOS avisa que é de "desenvolvedor não identificado" porque o programa não é
assinado; o clique com o botão direito autoriza uma vez.</li>
</ol>
<div class="aviso aviso-info"><p class="aviso-titulo">Se o macOS insistir</p>
<p>No Terminal: <code>xattr -dr com.apple.quarantine /Applications/BussolaPDV.app</code>. Isso remove
a marca de "baixado da internet" do próprio aplicativo.</p></div>
""",
            },
            {
                "id": "gerar-pacote",
                "titulo": "Gerar o pacote você mesmo (avançado)",
                "corpo": """
<p>Se você quer o instalador da sua versão, ou precisa do pacote para outro sistema, o projeto tem
uma receita única. Ela roda no sistema em que você está: não existe compilação cruzada — o
<code>.exe</code> nasce no Windows, o <code>.app</code> no macOS e o binário Linux no Linux.</p>
<pre><code>python empacotamento/gerar_pacote.py</code></pre>
<p>O resultado vai para <code>dist/</code>. Para os sistemas que você não tem, o GitHub Actions
compila por você (workflow <em>Pacotes</em>) e entrega como artefato do run. Passo a passo completo,
com os comandos manuais de cada sistema, em <code>docs/PACOTES.md</code>.</p>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 3
    {
        "id": "primeiro-uso",
        "titulo": "Primeira abertura",
        "resumo": "Criar a loja, o Admin Master e escolher onde a base vai ficar.",
        "icone": "🚪",
        "secoes": [
            {
                "id": "assistente",
                "titulo": "O assistente de primeiro uso",
                "corpo": """
<p>Na primeira vez que o programa abre, ele não tem banco de dados nenhum — então mostra um
formulário de instalação em vez da tela de login. É aqui que a loja nasce.</p>
<ol class="passos">
<li><strong>Nome da loja</strong>: o nome que aparece no topo do menu, no rodapé e no cupom.</li>
<li><strong>Usuário</strong>: o login do <strong>Admin Master</strong>. O padrão é <code>master</code>;
pode trocar, mas não esqueça.</li>
<li><strong>Nome do responsável</strong>: seu nome. Ele fica registrado em tudo o que você fizer.</li>
<li><strong>Senha</strong>: no mínimo 8 caracteres, e não pode ser um caractere só repetido. Use
letras e números; é a senha que manda em tudo.</li>
<li><strong>Confirmar senha</strong>: repetir, para não gravar errado.</li>
<li><strong>Pasta de dados</strong>: onde a base vai ficar. O programa sugere a pasta padrão do
sistema; o botão ao lado permite escolher outra — outro disco, um SSD separado ou um pendrive.</li>
</ol>
<div class="aviso aviso-perigo"><p class="aviso-titulo">Guarde a senha do Admin Master</p>
<p>Não existe tela de "esqueci minha senha" para esse usuário (é a pendência P11 do projeto). Se
perder a senha, a recuperação exige procedimento técnico no banco. Anote-a em lugar seguro, fora do
computador da loja.</p></div>
""",
                "imagem": (
                    "20_primeiro_uso.png",
                    "Assistente de primeiro uso. A faixa azul traz o logo do programa; abaixo, os "
                    "campos da loja e a pasta onde a base será guardada.",
                ),
            },
            {
                "id": "pasta-dados",
                "titulo": "A pasta de dados: onde sua loja realmente mora",
                "corpo": """
<p>Tudo o que o programa sabe está em um arquivo por pasta: a base (<code>pdv.db</code>), as cópias
de segurança (<code>copias/</code>), os relatórios exportados e os registros de erro.</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Sistema</th><th>Pasta padrão dos dados</th></tr></thead>
<tbody>
<tr><th scope="row">Windows</th><td><code>%LOCALAPPDATA%\\BussolaPDV</code></td></tr>
<tr><th scope="row">Linux</th><td><code>~/.local/share/bussola-pdv</code></td></tr>
<tr><th scope="row">macOS</th><td><code>~/Library/Application Support/BussolaPDV</code></td></tr>
</tbody></table></div>
<p>Onde você escolheu a pasta fica gravado num arquivo pequeno de configuração
(<code>instalacao.json</code>), fora da pasta de dados — se o ponteiro morasse dentro dela, mudar de
pasta perderia o ponteiro. Depois de instalado, dá para mudar a pasta em
<em>Parâmetros</em>; o programa copia a base para o novo lugar antes de passar a usá-lo.</p>
""",
                "avancado": """
<p>A precedência é: variável de ambiente <code>BUSSOLA_DADOS</code> &gt; pasta escolhida &gt; padrão do
sistema. A variável ganha porque é o que permite rodar duas instalações lado a lado, uma demonstração
em pendrive ou um teste isolado. Para apontar o arquivo de configuração para outro lugar:
<code>BUSSOLA_CONFIG</code>.</p>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 4
    {
        "id": "entrar",
        "titulo": "Entrar no programa",
        "resumo": "Login, perfis de acesso e o que cada perfil pode fazer.",
        "icone": "🔑",
        "secoes": [
            {
                "id": "login",
                "titulo": "A tela de login",
                "corpo": """
<p>Ao abrir o programa pela segunda vez em diante, aparece o cartão de login: usuário e senha. A
senha é conferida com <strong>Argon2id</strong> (um algoritmo lento de propósito, que dificulta
descobrir senha por tentativa) e <strong>nunca é gravada em texto</strong>. O programa também não diz
se o usuário existe: errar usuário ou senha dá a mesma mensagem.</p>
<p>Depois de 5 tentativas erradas o usuário fica bloqueado por 5 minutos — os dois números são
parâmetros da loja (<em>Parâmetros</em>).</p>
""",
                "imagem": (
                    "07_login.png",
                    "Cartão de login: a faixa azul leva o logo do programa (ou o logo da loja, se o "
                    "Admin Master enviou um em Marca e tema).",
                ),
            },
            {
                "id": "perfis",
                "titulo": "Os cinco perfis de acesso",
                "corpo": """
<p>Cada pessoa que usa o programa tem um <strong>perfil</strong>, e o perfil define o que ela pode
fazer. Isso não é enfeite: toda ação sensível é recusada no núcleo do programa, não só escondida na
tela.</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Perfil</th><th>Para quem</th><th>Em uma frase</th></tr></thead>
<tbody>
<tr><th scope="row">Atendente</th><td>quem fica no balcão</td><td>vende, abre e fecha caixa, recebe
suprimento, reimprime cupom. Não cancela venda, não mexe em cadastro.</td></tr>
<tr><th scope="row">Gerente</th><td>dono, encarregado</td><td>faz o do atendente e mais: cadastro de
produto e cliente, desconto acima do limite do operador, cancelamento, auditoria, backup.</td></tr>
<tr><th scope="row">Contabilidade</th><td>escritório de contabilidade</td><td>só leitura: relatórios,
fechamento, exportação e auditoria. Não vende, não altera cadastro.</td></tr>
<tr><th scope="row">Admin</th><td>administração da loja</td><td>quase tudo, inclusive
<em>Administração</em>: marca, usuários, parâmetros. Não altera a matriz de permissões.</td></tr>
<tr><th scope="row">Admin Master</th><td>responsável pelo sistema</td><td>tudo, inclusive a matriz de
permissões, restauração de backup e as tarefas de manutenção.</td></tr>
</tbody></table></div>
<p>A tela <em>Administração → Perfis e permissões</em> mostra a matriz completa (ação por perfil) e
permite ligar e desligar cada permissão. Abaixo, a mesma matriz em versão consultável — marque um
perfil para ver só as permissões dele.</p>
""",
                "demo": "permissoes",
            },
        ],
    },
    # ------------------------------------------------------------------ 5
    {
        "id": "tela",
        "titulo": "Conhecendo a tela",
        "resumo": "Menu, barra superior, indicadores, trilha e o que muda em tela pequena.",
        "icone": "🖥️",
        "secoes": [
            {
                "id": "partes-da-tela",
                "titulo": "As partes da tela",
                "corpo": """
<p>A tela tem sempre a mesma estrutura, em qualquer módulo — é o que permite trocar de assunto sem se
perder.</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Onde</th><th>O que é</th></tr></thead>
<tbody>
<tr><th scope="row">Menu lateral (esquerda)</th><td>os módulos. Em cima, o logo e o nome da loja;
abaixo, quem está logado e com qual perfil; no pé, o aviso de que toda alteração é auditada.</td></tr>
<tr><th scope="row">Barra superior</th><td>o botão <kbd>☰</kbd> que recolhe o menu, o nome do módulo
e, à direita, o usuário logado.</td></tr>
<tr><th scope="row">Cabeçalho do conteúdo</th><td>o título do módulo, uma linha explicando para que
ele serve e a trilha do caminho (ex.: <em>Início › PDV</em>).</td></tr>
<tr><th scope="row">Indicadores</th><td>os cartões coloridos do topo: número grande, rótulo e
ícone. Mudam de módulo para módulo.</td></tr>
<tr><th scope="row">Conteúdo</th><td>os cartões brancos com os blocos numerados (01, 02, 03…) na
ordem em que se faz.</td></tr>
<tr><th scope="row">Rodapé</th><td>nome da loja, o aviso "dados locais, sem emissão fiscal" e a
versão do programa.</td></tr>
</tbody></table></div>
<div class="aviso aviso-dica"><p class="aviso-titulo">Dica</p>
<p>O botão <kbd>☰</kbd> recolhe o menu para 62 px, deixando só os ícones — útil em monitor pequeno.
Passar o mouse no ícone mostra o nome do módulo.</p></div>
""",
                "imagem": (
                    "01_pdv_vazio.png",
                    "A tela do PDV com o caixa aberto e nenhum item. Repare nos blocos numerados: "
                    "01 identificar, 02 lançar produtos, 03 pagamento, 04 finalizar.",
                ),
            },
            {
                "id": "tela-pequena",
                "titulo": "Em tela pequena ou com escala do Windows",
                "corpo": """
<p>O programa se reorganiza pela largura disponível, em três faixas:</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Largura</th><th>O que acontece</th></tr></thead>
<tbody>
<tr><th scope="row">menos de 900 px</th><td>menu recolhido (só ícones), título compacto, margens
menores, indicadores em duas colunas.</td></tr>
<tr><th scope="row">900 a 1279 px</th><td>menu aberto, indicadores em três colunas.</td></tr>
<tr><th scope="row">1280 px ou mais</th><td>menu aberto, quatro indicadores por linha.</td></tr>
</tbody></table></div>
<p>Isso importa no balcão real: um monitor de 1366×768 com escala de 150% do Windows tem só 911×512
de espaço lógico. O programa mede a tela antes de abrir e nunca nasce maior do que ela.</p>
""",
                "imagem": (
                    "21_pdv_800x600.png",
                    "A mesma venda em 800×600: menu recolhido, blocos empilhados e nada cortado.",
                ),
            },
            {
                "id": "tema",
                "titulo": "A cara da loja: tema e logo",
                "corpo": """
<p>A cor do programa é escolhida em <em>Administração → Marca e tema</em>: há temas prontos (Bússola,
Grafite, Esmeralda, Noturno, Oceano) e a possibilidade de trocar cor por cor. O mesmo lugar recebe o
<strong>logo da loja</strong> (arquivo PNG): enviado o logo, ele passa a aparecer no login, na primeira
tela e no menu lateral; a área administrativa continua sempre com a marca do Bússola.</p>
<div class="aviso aviso-atencao"><p class="aviso-titulo">Contraste é medido, não escolhido a olho</p>
<p>Se a cor escolhida deixar texto ilegível, a tela avisa e o programa escurece ou clareia a tinta o
mínimo necessário (critério WCAG). O objetivo é simples: ninguém deve precisar adivinhar o total da
venda porque a cor do botão ficou parecida com a do texto.</p></div>
""",
                "imagem": (
                    "14_tema_personalizado.png",
                    "Marca e tema: dados da loja, escolha de logo, cores por função e a prévia de "
                    "acessibilidade com o contraste calculado.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 6
    {
        "id": "dia",
        "titulo": "O dia de trabalho",
        "resumo": "A ordem que evita retrabalho: abrir, vender, conferir, fechar.",
        "icone": "☀️",
        "secoes": [
            {
                "id": "ordem-do-dia",
                "titulo": "A ordem do dia",
                "corpo": """
<p>A sequência abaixo não é burocracia: cada passo existe porque a falta dele dá problema no fim do
dia. Se você abrir o turno errado, o fechamento não fecha. Se você vender sem turno, o programa
recusa.</p>
""",
                "guia": "inicio",
                "demo": "fluxo",
            },
        ],
    },
    # ------------------------------------------------------------------ 7
    {
        "id": "pdv",
        "titulo": "A venda (PDV)",
        "resumo": "Lance itens, aplique desconto dentro do limite, divida o pagamento e finalize.",
        "icone": "🛒",
        "secoes": [
            {
                "id": "venda-passo-a-passo",
                "titulo": "Passo a passo da venda",
                "corpo": """
<p>O PDV é a tela em que você passa o dia. Ela é dividida em quatro blocos numerados e a ordem é a
mesma sempre: identificar a venda, lançar produtos, receber o pagamento e finalizar.</p>
""",
                "guia": "pdv",
                "imagem": (
                    "02_pdv_com_itens.png",
                    "Venda em andamento: três itens lançados, subtotal, desconto aplicado e o total "
                    "em destaque no canto direito do bloco 04.",
                ),
            },
            {
                "id": "demonstracao-fluxo",
                "titulo": "Demonstração: a venda em cinco passos",
                "corpo": """
<p>Percorra a demonstração abaixo. Ela não é o programa — é um resumo clicável do caminho que você vai
fazer dezenas de vezes por dia, para fixar a ordem antes de encostar no caixa de verdade.</p>
""",
                "demo": "fluxo-venda",
            },
            {
                "id": "troco",
                "titulo": "Demonstração: conferindo o troco",
                "corpo": """
<p>O programa calcula o troco sozinho, mas conferir de cabeça é o que evita erro na correria. Use a
calculadora abaixo com os mesmos valores de uma venda de teste: digite o total e quanto o cliente
entregou (até três formas de pagamento, como no PDV).</p>
""",
                "demo": "troco",
            },
            {
                "id": "desconto",
                "titulo": "Desconto: o que cada perfil pode dar",
                "corpo": """
<p>Existem três limites, todos configuráveis em <em>Parâmetros</em>. Com os valores de fábrica:</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Quem</th><th>Limite</th><th>Acima disso</th></tr></thead>
<tbody>
<tr><th scope="row">Atendente</th><td>5%</td><td>precisa de autorização de gerente na hora</td></tr>
<tr><th scope="row">Gerente</th><td>15%</td><td>precisa de autorização do Admin Master</td></tr>
<tr><th scope="row">Autorização máxima</th><td>100%</td><td>acima disso o programa recusa</td></tr>
</tbody></table></div>
<p>A autorização é <strong>nominal</strong>: quem autorizou fica gravado na auditoria, junto com o
valor e o motivo. Não existe desconto "anônimo".</p>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 8
    {
        "id": "caixa",
        "titulo": "Caixa e gaveta",
        "resumo": "Abrir turno, sangria, suprimento, conferência e fechamento.",
        "icone": "💵",
        "secoes": [
            {
                "id": "caixa-turno",
                "titulo": "O turno de caixa",
                "corpo": """
<p>O turno é o "envelope" do dia: tudo o que entrar e sair da gaveta fica dentro dele. Um caixa tem
um turno aberto por vez; o programa não deixa abrir dois.</p>
""",
                "guia": "caixa",
                "imagem": (
                    "03_caixa.png",
                    "Módulo Caixa com o turno aberto: fundo de troco, vendas do turno, sangrias, "
                    "suprimentos e a conferência de cédulas por denominação.",
                ),
            },
            {
                "id": "conferencia",
                "titulo": "Conferência de cédulas e diferença",
                "corpo": """
<p>No fechamento o programa pede a quantidade de cada cédula e moeda, soma, compara com o esperado e
mostra a diferença. Diferença dentro da tolerância (R$ 5,00 de fábrica) fecha direto; acima disso,
exige <strong>justificativa escrita</strong> — que vai para a auditoria com o seu nome.</p>
<div class="aviso aviso-dica"><p class="aviso-titulo">Dica</p>
<p>Conte a gaveta antes de digitar. O programa não "adivinha" nada: ele só soma o que você informou e
compara com o que ele registrou de vendas, sangrias e suprimentos.</p></div>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 9
    {
        "id": "produtos",
        "titulo": "Produtos",
        "resumo": "Cadastro, preço, custo, estoque, ponto de pedido e busca.",
        "icone": "📦",
        "secoes": [
            {
                "id": "cadastro-produtos",
                "titulo": "Cadastro e consulta de produtos",
                "corpo": """
<p>O catálogo é a base de tudo: sem produto cadastrado não há venda, não há estoque e não há
relatório de reposição.</p>
<p class="dica">Esta tela <strong>consulta, exporta e imprime</strong>; criar ou alterar produto ainda depende de alguém com acesso técnico. Veja <a href="#nao-da-pela-tela">o que já tem botão e o que ainda não tem</a>.</p>
""",
                "guia": "produtos",
                "imagem": (
                    "04_produtos.png",
                    "Produtos: busca por descrição ou código, indicadores de estoque e a lista com "
                    "preço, custo, saldo e status de reposição.",
                ),
            },
            {
                "id": "codigo-barras",
                "titulo": "Código interno e código de barras",
                "corpo": """
<p>Cada produto tem um <strong>código interno</strong> (curto, que você digita) e pode ter um
<strong>código de barras</strong> (o que o leitor lê). No PDV, os dois funcionam no mesmo campo: digitar
<code>123</code> e apertar <kbd>Enter</kbd> é o mesmo que passar o leitor num produto com código de
barras 123.</p>
<p>Se dois produtos tiverem o mesmo código de barras, o programa recusa o cadastro — melhor descobrir
agora do que no meio da venda.</p>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 10
    {
        "id": "clientes",
        "titulo": "Clientes",
        "resumo": "Cadastro, documento, limite de crediário e histórico.",
        "icone": "🧑‍🤝‍🧑",
        "secoes": [
            {
                "id": "cadastro-clientes",
                "titulo": "Cadastro e consulta",
                "corpo": """
<p>Cliente é opcional na venda à vista e <strong>obrigatório</strong> na venda a prazo. O cadastro
guarda nome, documento, telefone e o limite de crediário.</p>
<p class="dica">Esta tela <strong>consulta, exporta e imprime</strong>; criar ou alterar cliente ainda depende de alguém com acesso técnico. Veja <a href="#nao-da-pela-tela">o que já tem botão e o que ainda não tem</a>.</p>
""",
                "guia": "clientes",
                "imagem": (
                    "16_clientes.png",
                    "Clientes: busca por nome ou documento, situação do cadastro e limite de "
                    "crediário disponível.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 11
    {
        "id": "crediario",
        "titulo": "Crediário",
        "resumo": "Títulos, parcelas, atraso e recebimento parcial.",
        "icone": "📝",
        "secoes": [
            {
                "id": "titulos",
                "titulo": "Títulos e parcelas",
                "corpo": """
<p>Venda a prazo gera um <strong>título</strong> com parcelas. O programa mostra o que está a vencer,
o que está atrasado e há quanto tempo — é o que permite cobrar sem planilha paralela.</p>
<p class="dica">A baixa de recebimento (dar a parcela como paga) ainda não tem botão nesta tela; o que ela faz é mostrar o que está em aberto e exportar. Veja <a href="#nao-da-pela-tela">o que já tem botão e o que ainda não tem</a>.</p>
""",
                "guia": "crediario",
                "imagem": (
                    "17_crediario.png",
                    "Crediário: títulos a receber, parcelas, classificação por atraso (aging) e "
                    "recebimento parcial ou total.",
                ),
            },
            {
                "id": "regras-crediario",
                "titulo": "As regras que o programa aplica",
                "corpo": """
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Regra</th><th>Valor de fábrica</th><th>Onde mudar</th></tr></thead>
<tbody>
<tr><th scope="row">Parcelas máximas por título</th><td>12</td><td>Parâmetros</td></tr>
<tr><th scope="row">Bloqueio de nova venda a prazo</th><td>com 30 dias de atraso</td><td>Parâmetros</td></tr>
<tr><th scope="row">Juros e encargos</th><td><strong>não existem</strong> (pendência P3)</td><td>—</td></tr>
</tbody></table></div>
<div class="aviso aviso-atencao"><p class="aviso-titulo">O limite é do cliente, e é conferido</p>
<p>Se o cliente já deve e o limite está estourado, o programa recusa a nova venda a prazo sem
autorização. Quem autoriza fica registrado na auditoria.</p></div>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 12
    {
        "id": "estoque",
        "titulo": "Estoque e entradas",
        "resumo": "Saldos, movimentos, ajustes e entrada de fornecedor.",
        "icone": "🏷️",
        "secoes": [
            {
                "id": "saldos",
                "titulo": "Saldos e movimentos",
                "corpo": """
<p>O estoque não é digitado: ele é a soma dos movimentos. Venda baixa, entrada de fornecedor sobe,
ajuste justifica a diferença. Por isso a tela mostra sempre os dois lados — o saldo e o que o
explicou.</p>
<p class="dica">Lançar entrada ou ajuste ainda não tem botão nesta tela: ela mostra o saldo e os movimentos que o explicam. Veja <a href="#nao-da-pela-tela">o que já tem botão e o que ainda não tem</a>.</p>
""",
                "guia": "estoque",
                "imagem": (
                    "18_estoque.png",
                    "Estoque: saldo por produto, movimentos que o explicam e o status de reposição.",
                ),
            },
            {
                "id": "entradas",
                "titulo": "Entrada de fornecedor",
                "corpo": """
<div class="aviso aviso-atencao"><p class="aviso-titulo">O módulo Entradas ainda não existe</p>
<p>Esta seção descreve o desenho previsto, <strong>não o que está disponível</strong>: o item
<em>Entradas</em> aparece no menu, mas a página não foi implementada nesta versão — e a tela Estoque
não lança movimento. Na prática, hoje, dar entrada de mercadoria depende do serviço técnico.</p></div>
<p><strong>Como está desenhado:</strong> escolher o fornecedor, informar produtos e quantidades e
confirmar; o estoque sobe na hora e o custo do produto é atualizado — é isso que faz o relatório de
margem ter sentido.</p>
<div class="aviso aviso-info"><p class="aviso-titulo">Estoque negativo</p>
<p>Vender sem saldo é permitido, mas exige autorização (pendência P5: confirmar se a loja aceita). O
movimento fica marcado, e o saldo fica negativo até a entrada regularizar.</p></div>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 13
    {
        "id": "vendas",
        "titulo": "Vendas do período",
        "resumo": "Histórico, segunda via do cupom e cancelamento controlado.",
        "icone": "🧾",
        "secoes": [
            {
                "id": "historico",
                "titulo": "Histórico e cancelamento",
                "corpo": """
<p>Toda venda finalizada fica no histórico, com data, operador, itens, formas de pagamento e total.
Cancelar não apaga: gera um evento de cancelamento, com motivo e autorizante, e a venda continua
aparecendo — riscada, mas visível.</p>
""",
                "guia": "vendas",
                "imagem": (
                    "29_vendas_911x512.png",
                    "Vendas do período numa janela estreita (911×512): a tabela mantém as colunas "
                    "essenciais e a rolagem horizontal aparece quando precisa.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 14
    {
        "id": "fechamento",
        "titulo": "Fechamento do dia",
        "resumo": "Relatório aritmético do dia e snapshot para conferência posterior.",
        "icone": "📅",
        "secoes": [
            {
                "id": "fechamento-dia",
                "titulo": "Conferir e fechar o dia",
                "corpo": """
<p>O fechamento mostra, em uma tela, o que entrou por forma de pagamento, o que foi cancelado, o que
saiu em sangria e o que sobrou de troco. Ele <strong>não é</strong> documento fiscal — é a conferência
aritmética do dia, que você pode exportar para o contador.</p>
""",
                "guia": "fechamento",
                "imagem": (
                    "05_fechamento.png",
                    "Fechamento: totais por forma de pagamento, cancelamentos, sangrias, suprimentos "
                    "e a diferença apurada.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 15
    {
        "id": "auditoria",
        "titulo": "Auditoria",
        "resumo": "A trilha que não deixa apagar o que aconteceu.",
        "icone": "🔍",
        "secoes": [
            {
                "id": "trilha",
                "titulo": "A trilha encadeada por hash",
                "corpo": """
<p>Todo evento sensível (venda, cancelamento, desconto autorizado, abertura e fechamento de caixa,
mudança de preço, alteração de permissão, backup) é gravado em ordem, e cada evento carrega o hash do
anterior. Isso tem uma consequência prática: <strong>apagar ou reescrever um evento quebra a
cadeia</strong>, e o programa mostra isso na tela.</p>
""",
                "guia": "auditoria",
                "imagem": (
                    "06_auditoria.png",
                    "Auditoria: eventos em ordem, com autor, valor e o estado da cadeia de hashes.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 16
    {
        "id": "relatorios",
        "titulo": "Relatórios, Excel, PDF e impressão",
        "resumo": "Levar o número para fora do programa — e para o papel.",
        "icone": "📤",
        "secoes": [
            {
                "id": "exportar",
                "titulo": "Exportar em Excel e PDF",
                "corpo": """
<p>Todo relatório com dado de loja tem, no canto do cartão, o botão <strong>Exportar</strong> com as
opções <em>Excel (.xlsx)</em> e <em>PDF</em>. O botão só aparece para quem tem a permissão
<em>Exportar dados</em>, e a exportação fica registrada na auditoria com o nome de quem exportou.</p>
<p>Telas que exportam: fechamento, vendas, catálogo, auditoria, crediário, clientes, estoque e turno de
caixa. Pela linha de comando dá para gerar os mesmos arquivos sem abrir a interface.</p>
""",
                "imagem": (
                    "19_caixa_exportar.png",
                    "O menu Exportar aberto no cartão do turno de caixa, com as opções Excel e PDF.",
                ),
                "avancado": """
<pre><code>python -m bussola_pdv.cli exportar --banco dados/pdv.db --tipo vendas \\
    --formato xlsx --de 2026-11-01 --ate 2026-11-30 --login gerente</code></pre>
<p>Tipos aceitos: <code>fechamento</code>, <code>vendas</code>, <code>catalogo</code>,
<code>auditoria</code>, <code>crediario</code>, <code>clientes</code>, <code>estoque</code>,
<code>turno</code>. Formatos: <code>xlsx</code> e <code>pdf</code>.</p>
""",
            },
            {
                "id": "imprimir",
                "titulo": "Imprimir: folha A4 e bobina térmica",
                "corpo": """
<p>O programa imprime em dois mundos diferentes, e a prévia mostra qual você está usando:</p>
<ul>
<li><strong>Impressora comum (A4)</strong> — para relatórios e conferências.</li>
<li><strong>Impressora térmica de bobina 58 mm ou 80 mm</strong> — para o cupom da venda, com corte de
papel, abertura de gaveta e código de barras, se a impressora suportar.</li>
</ul>
<p>A prévia de impressão deixa escolher papel, impressora, número de cópias e mostra o documento
desenhado antes de mandar para a máquina. Dá para imprimir, salvar em PDF ou salvar em TXT. A segunda
via do cupom sai pelo atalho <kbd>F8</kbd>, no PDV.</p>
<div class="aviso aviso-info"><p class="aviso-titulo">O que o projeto não afirma</p>
<p>A impressão foi implementada e testada no desenho e no arquivo gerado; <strong>não</strong> foi
validada em impressora térmica física por quem escreveu o programa. Antes de confiar no cupom no
balcão, imprima alguns em modo texto na sua impressora e confira largura, corte e gaveta.</p></div>
""",
                "imagem": (
                    "24_impressao_previa.png",
                    "Prévia de impressão: escolha de papel (58/80/A4), impressora, cópias e o "
                    "desenho do documento antes de imprimir.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 17
    {
        "id": "backup",
        "titulo": "Backup e restauração",
        "resumo": "A cópia que salva a loja quando o computador não abre.",
        "icone": "🛟",
        "secoes": [
            {
                "id": "backup-diario",
                "titulo": "Como o backup funciona",
                "corpo": """
<p>Uma vez por dia o programa cria uma cópia da base em arquivo, na pasta <code>copias/</code>, junto
com um <strong>manifesto</strong> que guarda o <code>sha256</code> da cópia. O manifesto serve para
responder à única pergunta que importa depois de um problema: "esta cópia está íntegra?".</p>
<p>A cópia automática mantém as 14 últimas. Cópia manual pode ser feita a qualquer momento em
<em>Administração → Manutenção</em>, e também existe uma ferramenta que funciona <strong>sem o
programa abrir</strong> — que é justamente o que se precisa quando ele não abre.</p>
""",
                "guia": "backup",
                "imagem": (
                    "13_admin_manutencao.png",
                    "Manutenção: cópias existentes, verificação de integridade, restauração e as "
                    "tarefas que só o Admin Master executa.",
                ),
                "avancado": """
<pre><code># copiar, listar, verificar e restaurar (não precisa do app aberto)
python ferramentas/backup_externo.py --banco "C:\\...\\pdv.db" --destino "D:\\copias" --criar
python ferramentas/backup_externo.py --destino "D:\\copias" --listar
python ferramentas/backup_externo.py --verificar "D:\\copias\\pdv-2026-11-14.db"
python ferramentas/backup_externo.py --banco "C:\\...\\pdv.db" --restaurar "D:\\copias\\pdv-2026-11-14.db"</code></pre>
<p>Criptografia: o backup <strong>não</strong> é criptografado (pendência P9). Guarde a pasta de cópias
em lugar com acesso restrito — ela contém os dados da loja.</p>
""",
            },
            {
                "id": "reinstalar",
                "titulo": "Trocar de computador ou reinstalar",
                "corpo": """
<ol class="passos">
<li><strong>Faça uma cópia</strong> (manual) e <strong>verifique</strong> a integridade dela.</li>
<li>Instale o programa na máquina nova — <strong>não</strong> crie loja nova no primeiro uso.</li>
<li>Abra <em>Administração → Manutenção</em> e restaure a cópia escolhida.</li>
<li>Confira o último fechamento e a auditoria: os dois devem terminar exatamente onde terminavam na
máquina antiga.</li>
</ol>
<div class="aviso aviso-perigo"><p class="aviso-titulo">Nunca copie a base com o programa aberto</p>
<p>Copiar o <code>pdv.db</code> com o programa em uso pode gerar arquivo inconsistente. Use a rotina de
backup do programa — ela fecha a transação antes de copiar.</p></div>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 18
    {
        "id": "administracao",
        "titulo": "Administração",
        "resumo": "Diagnóstico, marca, usuários, permissões, parâmetros e manutenção.",
        "icone": "⚙️",
        "secoes": [
            {
                "id": "secoes-admin",
                "titulo": "As seções da Administração",
                "corpo": """
<p>A área administrativa só aparece no menu para quem tem a permissão <em>Acessar administração</em>
(Admin e Admin Master). Ela é o único lugar do programa que <strong>não</strong> veste a marca da loja:
ali a identidade é sempre a do Bússola, e o logo enviado pela loja não aparece.</p>
""",
                "guia": "administracao",
                "imagem": (
                    "08_admin_dependencias.png",
                    "Visão geral da Administração: estado das dependências (Python, Qt, base de "
                    "dados), versão e atalhos para as demais seções.",
                ),
            },
            {
                "id": "usuarios",
                "titulo": "Usuários",
                "corpo": """
<p>Criar usuário é escolher login, nome, perfil e senha inicial. Desativar é melhor do que apagar:
o histórico de quem fez o quê continua fazendo sentido. Trocar o perfil de alguém vale a partir do
próximo login.</p>
""",
                "imagem": (
                    "10_admin_usuarios.png",
                    "Usuários: lista com perfil, situação e data do último acesso.",
                ),
            },
            {
                "id": "permissoes",
                "titulo": "Perfis e permissões",
                "corpo": """
<p>A matriz cruza as 32 ações do sistema com os cinco perfis. Ligar e desligar é imediato e auditado —
cada alteração registra quem mudou, de que para que. Só o <strong>Admin Master</strong> altera esta
matriz.</p>
""",
                "imagem": (
                    "11_admin_permissoes.png",
                    "Matriz de permissões: ações agrupadas por categoria e um perfil por coluna.",
                ),
            },
            {
                "id": "parametros",
                "titulo": "Parâmetros da operação",
                "corpo": """
<p>São os números que a loja decide: limites de desconto, parcelas do crediário, tolerância de
diferença no caixa, tentativas de senha, fuso horário, papel e impressora padrão. Quem altera precisa
da permissão <em>Alterar parâmetros</em>, e toda alteração é auditada.</p>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Parâmetro</th><th>De fábrica</th><th>Para que serve</th></tr></thead>
<tbody>
<tr><th scope="row">Desconto do operador</th><td>5%</td><td>até onde o atendente desconta sozinho</td></tr>
<tr><th scope="row">Desconto do gerente</th><td>15%</td><td>até onde o gerente desconta sozinho</td></tr>
<tr><th scope="row">Desconto máximo</th><td>100%</td><td>teto absoluto, com autorização</td></tr>
<tr><th scope="row">Parcelas do crediário</th><td>12</td><td>máximo de parcelas por título</td></tr>
<tr><th scope="row">Dias de atraso para bloquear</th><td>30</td><td>quando o cliente não compra mais a prazo</td></tr>
<tr><th scope="row">Tolerância de diferença no caixa</th><td>R$ 5,00</td><td>acima disso exige justificativa</td></tr>
<tr><th scope="row">Tentativas de senha</th><td>5</td><td>quantas antes do bloqueio</td></tr>
<tr><th scope="row">Minutos de bloqueio</th><td>5</td><td>tempo que a conta fica travada</td></tr>
<tr><th scope="row">Papel de impressão</th><td>bobina 80 mm</td><td>padrão da impressora da loja</td></tr>
</tbody></table></div>
""",
                "imagem": (
                    "12_admin_parametros.png",
                    "Parâmetros: valores atuais com a explicação de cada um, separados por assunto.",
                ),
            },
            {
                "id": "impressao-admin",
                "titulo": "Impressão (configuração)",
                "corpo": """
<p>A seção de impressão da Administração define motor (sistema ou direto), impressora, papel, cópias,
corte de papel, abertura de gaveta, código de barras e se o cupom sai automaticamente ao finalizar a
venda.</p>
""",
                "imagem": (
                    "25_admin_impressao.png",
                    "Configuração de impressão: escolha de impressora, papel e as opções de cupom.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 19
    {
        "id": "ajuda",
        "titulo": "Ajuda dentro do programa",
        "resumo": "F1, guia completo e o mentor que explica a tela.",
        "icone": "❓",
        "secoes": [
            {
                "id": "f1",
                "titulo": "O guia completo (F1) e o mentor",
                "corpo": """
<p>Aperte <kbd>F1</kbd> em qualquer tela: abre o guia com os mesmos temas deste manual, em versão
resumida e ligada à tela em que você está. O menu <em>Ajuda</em> faz o mesmo.</p>
<p>Na primeira vez em cada tela, aparece uma <strong>faixa do mentor</strong> no rodapé do conteúdo,
explicando o próximo passo e destacando com borda o campo de que está falando. Ela não cobre a tela e
não impede nada: se atrapalhar, clique em <em>Parar</em>. Para voltar a ver, o próprio guia tem
<em>Reativar o uso orientado</em>.</p>
""",
                "imagem": (
                    "30_mentor_pdv.png",
                    "O mentor no PDV: faixa no rodapé do conteúdo e o campo do passo destacado com "
                    "borda — sem máscara escura, sem bloquear a operação.",
                ),
            },
            {
                "id": "guia-completo",
                "titulo": "Guia completo e busca",
                "corpo": """
<p>O guia tem 14 temas, do "começando o dia" às mensagens de erro, com busca por palavra. É a mesma
fonte deste manual — o que está escrito aqui e o que aparece no <kbd>F1</kbd> não podem divergir.</p>
""",
                "imagem": (
                    "32_ajuda_guia.png",
                    "Guia completo: temas à esquerda, passos e tabela de campos à direita.",
                ),
            },
            {
                "id": "busca-guia",
                "titulo": "Buscar uma palavra",
                "corpo": """
<p>Procurando "sangria", "troco" ou "cancelar"? A busca do guia filtra temas pelo título e pelo texto
dos passos.</p>
""",
                "imagem": (
                    "33_ajuda_busca.png",
                    "Busca no guia: o termo digitado filtra os temas e mostra em qual passo ele "
                    "aparece.",
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ 20
    {
        "id": "problemas",
        "titulo": "Problemas comuns",
        "resumo": "As mensagens que aparecem e a atitude certa em cada uma.",
        "icone": "🩺",
        "secoes": [
            {
                "id": "mensagens",
                "titulo": "Mensagens do programa e o que fazer",
                "corpo": """
<p>Quando algo dá errado, o programa diz o que aconteceu e o que fazer. Abaixo, as mensagens mais
comuns — e o que realmente resolve cada uma.</p>
""",
                "guia": "problemas",
            },
            {
                "id": "nao-abre",
                "titulo": "O programa não abre",
                "corpo": """
<ol class="passos">
<li><strong>Windows:</strong> abra o <code>BussolaPDV-console.exe</code> (fica na mesma pasta). Ele é
igual, mas mostra a mensagem de erro em vez de fechar calado.</li>
<li><strong>Windows:</strong> se aparecer aviso do SmartScreen, é a assinatura digital ausente:
<em>Mais informações → Executar assim mesmo</em>.</li>
<li><strong>Base corrompida:</strong> o programa avisa e oferece restaurar uma cópia. Se ele não abrir
nem para isso, use o backup externo (capítulo 17) — ele não depende do programa.</li>
<li><strong>Fuso horário:</strong> se aparecer erro de fuso (<code>ZoneInfoNotFoundError</code>) numa
instalação feita "do código", falta o pacote <code>tzdata</code>:
<code>python -m pip install tzdata</code>.</li>
</ol>
<div class="aviso aviso-dica"><p class="aviso-titulo">Dica</p>
<p>Ao relatar um problema, mande a mensagem exata e a versão que aparece no rodapé. "Não funciona" não
dá o que investigar; "ao finalizar, apareceu 'Nenhum turno aberto'" dá.</p></div>
""",
            },
            {
                "id": "antivirus",
                "titulo": "Antivírus e SmartScreen reclamando",
                "corpo": """
<p>O executável não tem assinatura digital (é um certificado pago, anual). Sem assinatura, o Windows
mostra o aviso azul do SmartScreen e alguns antivírus desconfiam de executável novo. O que o projeto
faz para reduzir isso: nada de compressão UPX (que aumenta muito o falso positivo) e nenhuma chamada
de rede.</p>
<p>Se o antivírus bloquear, a decisão é sua: liberar a pasta do programa, ou usar a versão portátil em
uma pasta de dados separada. O código-fonte é público — qualquer um pode conferir o que o programa
faz.</p>
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 21
    {
        "id": "atalhos",
        "titulo": "Atalhos de teclado",
        "resumo": "As teclas que economizam o dia inteiro.",
        "icone": "⌨️",
        "secoes": [
            {
                "id": "teclas",
                "titulo": "Tabela de atalhos",
                "corpo": """
<p>Quem vende o dia inteiro não usa mouse. Estas são as teclas que existem hoje — e o que cada uma faz
de verdade.</p>
""",
                "guia": "atalhos",
                "demo": "atalhos",
            },
        ],
    },
    # ------------------------------------------------------------------ 22
    {
        "id": "avancado",
        "titulo": "Para usuário avançado",
        "resumo": "Linha de comando, arquivos, arquitetura, testes e como contribuir com código.",
        "icone": "🧰",
        "secoes": [
            {
                "id": "cli",
                "titulo": "Linha de comando",
                "corpo": """
<p>O mesmo núcleo do programa tem uma interface de linha de comando, útil para backup agendado,
exportação em lote e diagnóstico quando a interface não abre.</p>
<pre><code>python -m bussola_pdv.cli --help

bussola init        --banco dados/pdv.db --admin-login master   # cria a base
bussola demo        --banco dados/demo.db                       # base com dados fictícios
bussola info        --banco dados/pdv.db                        # versão, integridade, auditoria
bussola backup      --banco dados/pdv.db --destino D:\\copias --automatico
bussola fechamento  --banco dados/pdv.db --data 2026-11-11
bussola exportar    --banco dados/pdv.db --tipo vendas --formato pdf --login gerente</code></pre>
""",
            },
            {
                "id": "arquivos",
                "titulo": "Onde está cada arquivo",
                "corpo": """
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>O quê</th><th>Onde</th></tr></thead>
<tbody>
<tr><th scope="row">Base de dados</th><td><code>&lt;pasta de dados&gt;/pdv.db</code></td></tr>
<tr><th scope="row">Cópias de segurança</th><td><code>&lt;pasta de dados&gt;/copias/</code> (cada uma com manifesto)</td></tr>
<tr><th scope="row">Relatórios exportados</th><td><code>&lt;pasta de dados&gt;/relatorios/</code></td></tr>
<tr><th scope="row">Ponteiro da pasta de dados</th><td><code>instalacao.json</code> no diretório de configuração</td></tr>
<tr><th scope="row">Logs e diagnóstico</th><td><code>&lt;pasta de dados&gt;/logs/</code></td></tr>
</tbody></table></div>
<p>Variáveis de ambiente reconhecidas: <code>BUSSOLA_DADOS</code> (pasta de dados),
<code>BUSSOLA_CONFIG</code> (onde fica o <code>instalacao.json</code>),
<code>BUSSOLA_SENHA</code> e <code>BUSSOLA_SENHA_ADMIN</code> (senha em script, evitando digitar).</p>
""",
            },
            {
                "id": "arquitetura",
                "titulo": "Como o código está organizado",
                "corpo": """
<p>O projeto é Python 3.12+, com três camadas e uma regra: <strong>regra de negócio não conhece
Qt</strong>.</p>
<ul>
<li><code>dominio/</code> — dinheiro, venda, pagamentos, caixa, produto, cliente, crediário, usuário,
permissões. Nada de interface.</li>
<li><code>aplicacao/</code> — os casos de uso (vender, abrir caixa, fechar turno, exportar, backup) e a
autorização por permissão.</li>
<li><code>infra/</code> — SQLite, migrações versionadas, repositórios.</li>
<li><code>ui/</code> — PySide6: janelas, telas, tema, impressão, exportação, ajuda.</li>
<li><code>tests/</code> — a suíte completa; binário e instalador nascem no CI.</li>
</ul>
<p>As decisões de engenharia estão registradas em <code>docs/DECISOES.md</code> (28 ADRs), incluindo as
que foram tomadas contra a primeira ideia — como "cor com contraste medido, não a olho" e "o mentor
aponta pelo nome do widget, não por coordenada".</p>
""",
                "avancado": """
<pre><code>git clone https://github.com/davidcreator/bussolapdv
cd bussolapdv
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
make test          # suíte completa (Qt offscreen)
make lint tipos    # ruff e mypy
make responsivo    # mede a interface de 640x440 até 2560x1440
make capturas      # regenera as imagens deste manual
make pacote        # gera o instalador do sistema atual</code></pre>
""",
            },
            {
                "id": "contribuir",
                "titulo": "Contribuir e apoiar",
                "corpo": """
<p>O projeto é open source e o código é público: <a href="https://github.com/davidcreator/bussolapdv">
github.com/davidcreator/bussolapdv</a>. Relato de defeito, sugestão de melhoria e código são bem-vindos;
o arquivo <code>CONTRIBUINDO.md</code> explica as regras que o projeto não abre mão (teste rodado,
mensagem de erro que explica, nada de rede) e como apoiar financeiramente.</p>
<div class="aviso aviso-info"><p class="aviso-titulo">Sobre doações</p>
<p>Os campos de recebimento (PIX, banco, PayPal) estão no <code>CONTRIBUINDO.md</code> como
<code>«PREENCHER»</code> até o responsável informar os dados reais. Enquanto houver esse marcador,
<strong>nenhuma doação deve ser enviada</strong> — e o projeto nunca pede senha, token ou acesso remoto à
sua base.</p></div>
<p>Licença: <strong>GPL-2.0-or-later</strong>.</p>
<p class="assinatura">Manual gerado a partir do próprio programa — versão {VERSAO}. As capturas de tela
foram produzidas com a massa de demonstração fictícia; nenhum dado de loja real aparece aqui.</p>
""",
            },
        ],
    },
]
