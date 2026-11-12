"""Guia de uso do PDV: o texto que o mentor mostra, tela por tela e campo por campo.

Por que o conteúdo vive no código e não num arquivo de ajuda externo:

* **não pode mentir.** O guia é escrito junto da tela que ele descreve; quando um
  campo muda de nome, o teste `tests/test_ajuda.py` compara o guia com o widget de
  verdade e falha. Guia desatualizado é pior do que guia nenhum — ele ensina errado.
* **não pode sumir.** Offline, sem servidor de documentação, sem navegador: uma loja
  em `D:\\pdv` sem rede continua com o guia completo no menu.
* **serve a três saídas.** A mesma estrutura vira a janela de Ajuda (HTML), o
  arquivo exportável (Markdown) e o balão do modo guiado (passos com destaque).

Nada aqui executa regra de negócio: é texto, ordem de leitura e explicação de campo.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contexto import Contexto

#: Chave do parâmetro que guarda se o uso orientado está ligado.
CHAVE_GUIADO = "ajuda.guiado"
CHAVE_VERSAO = "ajuda.versao"

#: Versão do guia. Subir quando o conteúdo mudar de forma relevante: é o que faz o
#: mentor reaparecer para quem já tinha concluído o tour de uma versão anterior.
VERSAO_GUIA = 1


@dataclass(frozen=True, slots=True)
class Campo:
    """Um campo (ou coluna, ou botão) da tela, explicado em uma frase útil."""

    rotulo: str
    o_que_e: str
    como_usar: str = ""


@dataclass(frozen=True, slots=True)
class Passo:
    """Um passo do modo guiado.

    `alvo` é o **nome do atributo** do widget na tela (ex.: `campo_codigo`); o
    mentor destaca a borda dele. Sem `alvo`, o passo é só texto.
    """

    titulo: str
    texto: str
    alvo: str | None = None


@dataclass(frozen=True, slots=True)
class Tema:
    chave: str
    titulo: str
    icone: str
    resumo: str
    quando: str = ""
    passos: tuple[Passo, ...] = ()
    campos: tuple[Campo, ...] = ()
    atalhos: tuple[tuple[str, str], ...] = ()
    cuidados: tuple[str, ...] = ()
    relacionados: tuple[str, ...] = ()
    #: Nome do módulo da janela principal que este tema acompanha (para o tour).
    modulo: str | None = None


GUIA: tuple[Tema, ...] = (
    # ---------------------------------------------------------------- começo
    Tema(
        "inicio",
        "Começando o dia",
        "visao",
        "A ordem que evita retrabalho: abrir o turno, vender, conferir a gaveta e fechar.",
        quando="Use na primeira vez em que a máquina é ligada ou quando alguém assume o caixa.",
        passos=(
            Passo("Abra o turno", "Sem turno aberto o PDV não finaliza venda: a tela avisa e "
                  "oferece o atalho para o Caixa.", "botao_finalizar"),
            Passo("Confira o fundo de troco", "O valor que você informa na abertura é o "
                  "esperado na gaveta no fim do dia, junto com as vendas em dinheiro.", None),
            Passo("Venda", "Código, quantidade, pagamento e F4. O cupom é interno: não é "
                  "documento fiscal.", "campo_codigo"),
            Passo("Feche o dia", "No Caixa, 'Conferir e fechar': conte as cédulas e moedas. "
                  "Diferença exige justificativa escrita.", None),
        ),
        campos=(
            Campo("Usuário e senha", "Seu acesso pessoal. Cada ação fica registrada no seu nome.",
                  "Nunca use o login de outra pessoa: a auditoria mostra quem fez."),
            Campo("Perfil", "O que você pode fazer. Atendente vende; gerente autoriza; admin "
                  "administra.", "Se um botão não existe para você, é o perfil — peça ao Admin Master."),
        ),
        cuidados=(
            "O sistema é offline por decisão de projeto: nada é enviado para fora da máquina.",
            "Todo dado mora na pasta escolhida na instalação. Faça cópia de segurança (menu "
            "Administração → Manutenção, ou a ferramenta `Backup\\backup_externo.bat`).",
        ),
        relacionados=("pdv", "caixa", "backup"),
    ),
    # ---------------------------------------------------------------- PDV
    Tema(
        "pdv",
        "PDV — frente de caixa",
        "pdv",
        "Lance os itens, aplique desconto dentro do seu limite, divida o pagamento e finalize.",
        quando="Toda venda de balcão. É a tela que abre primeiro, com o turno já iniciado.",
        passos=(
            Passo("1. Identifique a venda", "O operador logado aparece à esquerda; o cliente é "
                  "opcional e serve para crediário e histórico.", "campo_cliente"),
            Passo("2. Lance o produto", "Digite o código interno ou passe o leitor de código de "
                  "barras e tecle Enter: o item entra na lista.", "campo_codigo"),
            Passo("Quantidade", "Começa em 1. Troque antes de adicionar para lançar mais de uma "
                  "unidade do mesmo item.", "campo_quantidade"),
            Passo("3. Ajuste o que precisar", "Na lista você confere preço, desconto e total de "
                  "cada linha; Delete remove a linha selecionada.", "tabela"),
            Passo("4. Pagamento", "Até três formas na mesma venda. Dinheiro aceita troco; PIX e "
                  "cartão nascem pendentes até a confirmação.", "formulario_pagamento"),
            Passo("5. Finalize", "F4 (ou o botão) grava a venda, baixa o estoque, gera o título "
                  "do crediário e lança na auditoria — tudo de uma vez, ou nada.", "botao_finalizar"),
        ),
        campos=(
            Campo("Código", "Código interno ou código de barras do produto.",
                  "F2 leva o cursor para cá; Enter adiciona. Código inexistente mostra o motivo, "
                  "não um item qualquer."),
            Campo("Qtd", "Quantidade da linha que está sendo lançada.", "Aceita decimais com "
                  "vírgula para itens vendidos por peso (ex.: 0,750)."),
            Campo("Adicionar", "Coloca o item no cupom.", "Mesmo efeito do Enter no campo de código."),
            Campo("Colunas da lista", "Código, Descrição, Qtd, Un., Preço, Desc. e Total.",
                  "Desc. é o desconto daquela linha; Total é o que entra na soma do cupom."),
            Campo("Cliente", "Cliente da venda (opcional).", "'Buscar cliente' procura por nome ou "
                  "documento; obrigatório para vender no crediário."),
            Campo("Forma", "Dinheiro, PIX, cartão ou crediário.", "A primeira linha já vem escolhida; "
                  "use as outras duas quando o cliente dividir."),
            Campo("Valor", "Quanto foi pago naquela forma.", "O que passa do total em dinheiro vira "
                  "troco; PIX e cartão não geram troco."),
            Campo("Troco", "Diferença entre o pago em dinheiro e o total.", "Fica em vermelho quando "
                  "falta valor."),
            Campo("Total", "Soma do cupom, já com descontos.", "Ao lado das ações de finalizar."),
            Campo("Itens no cupom / Desconto / Pagamento",
                  "Os três indicadores do topo: unidades lançadas, desconto aplicado e quanto ainda "
                  "falta pagar.", "Servem de conferência rápida antes do F4."),
        ),
        atalhos=(
            ("F2", "Vai para o campo de código do produto"),
            ("Enter", "Adiciona o item (no campo de código ou de quantidade)"),
            ("Delete", "Remove a linha selecionada da lista"),
            ("F4", "Finaliza a venda"),
            ("F6", "Cancela o cupom inteiro"),
            ("F8", "Reimprime o cupom da última venda desta estação"),
            ("Esc", "Limpa a mensagem de erro da tela"),
            ("F1", "Abre esta Ajuda"),
        ),
        cuidados=(
            "Cancelar o cupom (F6) descarta o que está na tela; nada é gravado.",
            "Desconto acima do seu limite pede autorização de gerente na hora.",
            "Venda com estoque insuficiente também pede autorização — e fica registrada.",
        ),
        relacionados=("caixa", "vendas", "problemas"),
        modulo="PDV",
    ),
    # ---------------------------------------------------------------- Caixa
    Tema(
        "caixa",
        "Caixa — turno e gaveta",
        "caixa",
        "Abrir o turno, registrar sangria e suprimento, conferir as cédulas e fechar com justificativa.",
        quando="Ao começar o dia (abertura) e ao encerrar (conferência). Sangria e suprimento, "
        "durante o expediente.",
        passos=(
            Passo("Abra o turno com o fundo de troco", "É o dinheiro que já está na gaveta. Vira "
                  "a base do 'esperado' no fechamento.", "botao_abrir"),
            Passo("Sangria e suprimento", "Sangria tira dinheiro da gaveta (depósito, cofre); "
                  "suprimento coloca (mais troco). Os dois pedem autorização e motivo.",
                  "botao_sangria"),
            Passo("Acompanhe o turno", "'Esperado na gaveta' = fundo + vendas em dinheiro − sangrias "
                  "+ suprimentos.", "rotulo_resumo"),
            Passo("Confira e feche", "Conte cédula por cédula na tabela de denominações; a diferença "
                  "aparece na hora e o fechamento exige motivo se houver.", "botao_fechar"),
        ),
        campos=(
            Campo("Abrir turno", "Inicia o turno do caixa com o fundo de troco informado.",
                  "Só existe um turno aberto por caixa por vez."),
            Campo("Sangria", "Retirada de dinheiro da gaveta.", "Gerente/master autoriza; o motivo "
                  "é obrigatório e vai para a auditoria."),
            Campo("Suprimento", "Colocação de dinheiro na gaveta.", "Mesmas regras da sangria."),
            Campo("Movimentos do turno", "Tipo, Valor e Motivo de cada sangria/suprimento.",
                  "Confira antes de fechar: é o que explica a diferença."),
            Campo("Denominação", "Cédulas e moedas de R$ 200,00 a R$ 0,01.",
                  "Informe quantas de cada. Zero nas que não existem na gaveta."),
            Campo("Quantidade", "Quantas unidades daquela denominação você contou.",
                  "Digite direto ou use as setas; o total soma na hora."),
            Campo("Esperado na gaveta", "O que o sistema calcula que deveria haver.",
                  "É comparação aritmética: não confirma PIX nem cartão no banco."),
            Campo("Contado", "Soma da sua contagem pelas denominações.", "Atualiza a cada digitação."),
            Campo("Diferença", "Contado − esperado.", "Sobra ou falta; exibida em reais e sinalizada."),
            Campo("Observação do conferente", "Motivo escrito da diferença.",
                  "Obrigatório quando há diferença — sem ele o fechamento não é aceito."),
        ),
        cuidados=(
            "Fechar o turno sem contar é possível, mas o 'contado' fica zero e a falta aparece "
            "inteira: conte antes.",
            "O fechamento e a conferência podem ser exportados (Excel/PDF) e impressos.",
        ),
        relacionados=("pdv", "fechamento", "backup"),
        modulo="Caixa",
    ),
    # ---------------------------------------------------------------- Produtos
    Tema(
        "produtos",
        "Produtos — cadastro e consulta",
        "produtos",
        "Lista o catálogo com preço, custo, estoque atual, ponto de pedido e status.",
        quando="Para conferir preço/estoque antes de vender ou para achar um produto pelo nome.",
        passos=(
            Passo("Busque", "Por código, código de barras ou descrição — a lista filtra enquanto "
                  "você digita.", "campo_busca"),
            Passo("Leia o status", "Ruptura, baixo, reposição ou OK compara o saldo com o ponto de "
                  "pedido de cada produto.", "tabela"),
            Passo("Exporte ou imprima", "Os botões do cartão geram a mesma consulta em Excel, PDF "
                  "ou na impressora.", None),
        ),
        campos=(
            Campo("Busca", "Filtro por código, código de barras ou descrição.",
                  "Vazio mostra o catálogo inteiro."),
            Campo("Status", "Ruptura (saldo zero), baixo (abaixo do ponto de pedido), reposição "
                  "e OK.", "Serve para a lista de compras do dia."),
        ),
        relacionados=("estoque", "pdv"),
        modulo="Produtos",
    ),
    # ---------------------------------------------------------------- Vendas
    Tema(
        "vendas",
        "Vendas — histórico e cancelamento",
        "vendas",
        "Histórico do período, segunda via do cupom e cancelamento com autorização e motivo.",
        quando="Quando o cliente volta para pedir a 2ª via ou quando é preciso cancelar uma venda.",
        passos=(
            Passo("Escolha o período", "De e Até limitam o que aparece; 'Filtrar' aplica.",
                  "data_ini"),
            Passo("Selecione a venda", "A lista traz Cupom, Data, Operador, Cliente, Itens, Total, "
                  "Aplicado e Status.", "tabela"),
            Passo("2ª via", "'Reimprimir cupom' monta o cupom a partir do que está gravado no banco "
                  "(não é uma cópia da tela).", "botao_reimprimir"),
            Passo("Cancelar", "Só venda concluída, com autorização de quem pode e motivo escrito; "
                  "o cancelamento devolve o estoque e entra na auditoria.", "botao_cancelar"),
        ),
        campos=(
            Campo("De / Até", "Intervalo de datas do histórico.", "O padrão é os últimos 30 dias."),
            Campo("Status", "Concluída, cancelada ou pendente de confirmação eletrônica.",
                  "PIX/cartão podem ficar pendentes até alguém confirmar."),
            Campo("Aplicado", "Quanto do total já foi pago efetivamente.",
                  "Em venda com pagamento pendente, é menor que o Total."),
        ),
        cuidados=(
            "Cancelamento não apaga: ele marca a venda e registra o evento na trilha.",
            "Reimprimir não duplica venda — só o papel.",
        ),
        relacionados=("pdv", "auditoria"),
        modulo="Vendas",
    ),
    # ---------------------------------------------------------------- Fechamento
    Tema(
        "fechamento",
        "Fechamento do dia",
        "fechamento",
        "Relatório aritmético do dia e snapshot versionado para conferência posterior.",
        quando="No fim do expediente, depois de fechar o caixa.",
        passos=(
            Passo("Escolha a data de negócio", "É a data comercial, aquela em que a venda 'conta'.",
                  "data"),
            Passo("Gere o fechamento", "O texto mostra totais por forma de pagamento, sangrias e "
                  "diferenças.", "texto"),
            Passo("Registre o snapshot", "Guarda uma foto do fechamento (com hash) para provar "
                  "depois o que foi conferido naquele dia.", "botao_registrar"),
        ),
        campos=(
            Campo("Data de negócio", "Data comercial do relatório.",
                  "Venda feita 23h55 pode pertencer ao dia anterior se assim foi configurado."),
            Campo("Registrar snapshot", "Congela o relatório do dia no banco.",
                  "Um dia pode ter mais de um snapshot; o primeiro é o retrato do fechamento."),
        ),
        cuidados=(
            "Fechamento não confirma dinheiro em banco: PIX e cartão dependem do extrato da "
            "adquirente.",
        ),
        relacionados=("caixa", "auditoria"),
        modulo="Fechamento",
    ),
    # ---------------------------------------------------------------- Auditoria
    Tema(
        "auditoria",
        "Auditoria — trilha do que aconteceu",
        "auditoria",
        "Todo evento sensível fica gravado em ordem, com hash encadeado: não dá para apagar nem "
        "reescrever sem quebrar a cadeia.",
        quando="Quando algo não fecha e é preciso saber quem fez, quando e com qual valor.",
        passos=(
            Passo("Veja os eventos", "Os mais recentes primeiro: ação, ator, entidade e detalhe.",
                  "tabela"),
            Passo("Verifique a cadeia", "Recalcula os hashes de ponta a ponta; se algo foi alterado "
                  "por fora, a verificação aponta a quebra.", "botao_verificar"),
        ),
        campos=(
            Campo("Evento", "Ação registrada (venda, cancelamento, sangria, login, alteração de "
                  "cadastro...).", "É a lista fechada de ações sensíveis do sistema."),
            Campo("Hash", "Impressão digital do evento, encadeada com o anterior.",
                  "Qualquer alteração de uma linha quebra a cadeia dali para frente."),
        ),
        relacionados=("vendas", "administracao"),
        modulo="Auditoria",
    ),
    # ---------------------------------------------------------------- Clientes
    Tema(
        "clientes",
        "Clientes",
        "clientes",
        "Consulta de clientes por nome ou documento, com limite de crediário e situação.",
        quando="Ao vender no crediário ou conferir o cadastro de alguém.",
        passos=(
            Passo("Busque por nome ou documento", "O documento aparece mascarado na tela.",
                  "campo_busca"),
            Passo("Leia a situação", "Ativo, limite de crédito e títulos em aberto.",
                  "tabela"),
        ),
        campos=(
            Campo("Documento", "CPF/CNPJ do cliente.", "Exibido mascarado: a tela não é lugar de "
                  "espalhar documento."),
            Campo("Limite de crédito", "Quanto o cliente pode comprar a prazo.",
                  "A compra é bloqueada quando o limite é atingido."),
        ),
        relacionados=("crediario",),
        modulo="Clientes",
    ),
    # ---------------------------------------------------------------- Crediário
    Tema(
        "crediario",
        "Crediário — títulos e parcelas",
        "crediario",
        "Títulos a receber, parcelas, aging por atraso e recebimento parcial ou total.",
        quando="Para receber uma parcela ou ver quem está em atraso.",
        passos=(
            Passo("Filtre", "'incluir títulos já recebidos' mostra também o histórico.",
                  "incluir_pagos"),
            Passo("Escolha o título", "A tabela traz cliente, vencimento, valor, dias de atraso e "
                  "status.", "tabela"),
            Passo("Receba", "O recebimento aceita valor parcial; o que sobrar continua em aberto.",
                  None),
        ),
        campos=(
            Campo("Dias de atraso", "Quantos dias o título está vencido hoje.",
                  "Base do aging 1–30 / 31–60 / 61–90 / >90."),
            Campo("Status", "Em aberto, parcial, recebido ou em atraso.",
                  "Atraso acima do limite configurado bloqueia nova compra a prazo."),
        ),
        cuidados=("Não há encargo por atraso: o sistema não inventa juros. O que não está "
                  "definido fica de fora, com o valor original.",),
        relacionados=("clientes", "pdv"),
        modulo="Crediário",
    ),
    # ---------------------------------------------------------------- Estoque
    Tema(
        "estoque",
        "Estoque — movimentos e saldos",
        "estoque",
        "Saldo por produto, movimentos que o explicam e status de reposição.",
        quando="Para saber por que um saldo está como está (entrada, venda, perda, ajuste).",
        passos=(
            Passo("Busque o produto", "Por código, código de barras ou descrição.", "campo_busca"),
            Passo("Veja o saldo e o status", "A coluna de status compara com o ponto de pedido.",
                  "tabela"),
        ),
        campos=(
            Campo("Movimentos", "Entradas, saídas por venda, ajustes e perdas.",
                  "O saldo é a soma assinada dos movimentos — não é um número solto."),
            Campo("Ponto de pedido", "Saldo a partir do qual o produto pede reposição.",
                  "Abaixo dele, o status muda para 'reposição' ou 'baixo'."),
        ),
        relacionados=("produtos",),
        modulo="Estoque",
    ),
    # ---------------------------------------------------------------- Administração
    Tema(
        "administracao",
        "Administração — as seis seções",
        "administracao",
        "Diagnóstico, marca, usuários, permissões, parâmetros e manutenção (backup).",
        quando="Só para quem tem permissão administrativa. Toda alteração é auditada.",
        passos=(
            Passo("Visão geral", "Checagens reais: integridade do banco, esquema, Admin Master "
                  "ativo, trilha de auditoria.", None),
            Passo("Marca e tema", "Nome, contato, logo, cores e tipografia — com prévia e aviso "
                  "quando o contraste fica abaixo de AA.", None),
            Passo("Usuários", "Criar, ativar, desativar e redefinir senha conforme a hierarquia.",
                  None),
            Passo("Perfis e permissões", "Matriz do que cada perfil pode fazer; só o Admin Master "
                  "altera.", None),
            Passo("Parâmetros", "Descontos, crediário, caixa, segurança e impressão.", None),
            Passo("Manutenção", "Cópias de segurança: criar, listar, verificar e restaurar.", None),
        ),
        campos=(
            Campo("Admin Master", "O dono da instalação; define o que cada perfil pode.",
                  "A senha dele é a chave da loja: guarde fora do computador."),
            Campo("Perfis", "Admin master, admin, gerente, atendente e contabilidade.",
                  "Cada perfil só vê o que o Admin Master liberou."),
        ),
        cuidados=(
            "Não existe tela de recuperação do Admin Master: a saída é procedimento no banco "
            "(documentado). Escolha a senha com cuidado.",
        ),
        relacionados=("backup", "inicio"),
        modulo="Administração",
    ),
    # ---------------------------------------------------------------- backup
    Tema(
        "backup",
        "Backup e reinstalação",
        "manutencao",
        "Cópia do banco em arquivo + manifesto com sha256, automática uma vez por dia.",
        quando="Antes de atualizar o programa, trocar de máquina ou quando algo deu errado.",
        passos=(
            Passo("Cópia automática", "Ao abrir, o sistema faz uma cópia por dia em "
                  "`Backup\\automatico`. Falha de backup nunca impede a loja de abrir — vira aviso.",
                  None),
            Passo("Cópia manual", "Administração → Manutenção gera o arquivo com manifesto.",
                  None),
            Passo("Sem o programa", "Com a base corrompida ou o app quebrado, use "
                  "`Backup\\backup_externo.bat criar|listar|verificar|restaurar|recuperar` (só Python "
                  "padrão).", None),
            Passo("Sem Python", "A última saída é copiar a pasta `%LOCALAPPDATA%\\BussolaPDV` pelo "
                  "Explorador.", None),
        ),
        campos=(
            Campo("Manifesto", "Arquivo `.manifesto.json` ao lado de cada cópia, com data, tamanho "
                  "e sha256.", "É o que prova que o arquivo não veio corrompido."),
        ),
        cuidados=(
            "Guarde as cópias em outra unidade/disco. Cópia no mesmo HD não protege de defeito "
            "no HD.",
            "Restaurar substitui a base atual: faça uma cópia antes de restaurar.",
        ),
        relacionados=("administracao", "inicio"),
    ),
    # ---------------------------------------------------------------- problemas
    Tema(
        "problemas",
        "Mensagens de erro e o que fazer",
        "aviso",
        "As mensagens que a operação vê e a atitude certa em cada uma.",
        quando="Quando aparece uma faixa vermelha na tela e você não sabe se pode continuar.",
        campos=(
            Campo("Abra o turno antes de vender",
                  "O caixa não tinha turno aberto.", "Vá em Caixa → Abrir turno e informe o fundo."),
            Campo("Estoque insuficiente",
                  "O saldo não cobre a quantidade lançada.",
                  "Chame quem pode autorizar (gerente); a venda fica registrada como exceção."),
            Campo("Desconto acima do limite",
                  "O desconto passa do que o seu perfil permite.",
                  "Autorize com um usuário de limite maior; o desconto concedido fica na auditoria."),
            Campo("Autorização negada", "Quem autorizou não tem a permissão daquela ação.",
                  "Confira o perfil: certas ações são exclusivas de admin master."),
            Campo("Turno já aberto neste caixa", "Existe turno em andamento.",
                  "Feche o turno atual antes de abrir outro."),
            Campo("Diferença exige justificativa",
                  "A contagem não bateu e a observação está vazia.",
                  "Escreva o motivo real (troco trocado, venda não lançada...) — é o que a "
                  "auditoria vai ler."),
            Campo("Base em uso por outro processo",
                  "Dois programas abertos na mesma base.", "Feche o outro; nunca copie a base aberta."),
        ),
        relacionados=("inicio", "caixa", "backup"),
    ),
    # ---------------------------------------------------------------- atalhos
    Tema(
        "atalhos",
        "Atalhos e navegação",
        "menu",
        "Teclas que economizam o dia inteiro e como o menu se comporta em tela pequena.",
        quando="Para quem opera o dia inteiro no teclado.",
        atalhos=(
            ("F1", "Ajuda (esta janela)"),
            ("F2", "Campo de código do produto (PDV)"),
            ("F4", "Finalizar venda"),
            ("F6", "Cancelar cupom"),
            ("F8", "Reimprimir o último cupom"),
            ("Delete", "Remove a linha selecionada"),
            ("Esc", "Limpa a mensagem"),
            ("Ctrl+B", "Recolhe/expande o menu lateral"),
        ),
        cuidados=(
            "Em tela estreita o menu vira uma faixa de ícones: passe o mouse para ver o nome.",
            "O mentor (uso orientado) pode ser religado a qualquer momento nesta janela.",
        ),
        relacionados=("inicio", "pdv"),
    ),
)

POR_CHAVE: dict[str, Tema] = {tema.chave: tema for tema in GUIA}

#: Tema que acompanha cada módulo da janela principal (usado pelo mentor).
TEMA_DO_MODULO: dict[str, str] = {
    tema.modulo: tema.chave for tema in GUIA if tema.modulo
}


def tema(chave: str) -> Tema | None:
    return POR_CHAVE.get(chave)


def temas() -> tuple[Tema, ...]:
    return GUIA


def buscar(texto: str) -> tuple[Tema, ...]:
    """Temas cujo texto (título, resumo, campos, atalhos) contém o termo.

    Busca simples e previsível de propósito: sem acento e sem caixa, comparando
    tudo o que a pessoa lê na tela — nada de esconder resultado atrás de ranking.
    """
    termo = _simplificar(texto)
    if not termo:
        return GUIA
    achados: list[Tema] = []
    for item in GUIA:
        if termo in _simplificar(_texto_do_tema(item)):
            achados.append(item)
    return tuple(achados)


def _simplificar(texto: str) -> str:
    from unicodedata import normalize

    sem_acento = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def _texto_do_tema(item: Tema) -> str:
    partes = [item.titulo, item.resumo, item.quando]
    partes += [f"{passo.titulo} {passo.texto}" for passo in item.passos]
    partes += [f"{campo.rotulo} {campo.o_que_e} {campo.como_usar}" for campo in item.campos]
    partes += [f"{tecla} {descricao}" for tecla, descricao in item.atalhos]
    partes += list(item.cuidados)
    return " ".join(partes)


# --------------------------------------------------------------------- renderização
def tema_em_html(item: Tema, *, titulo_html: bool = True) -> str:
    """HTML do tema para a janela de Ajuda (rich text do Qt)."""
    from html import escape

    e = escape
    partes: list[str] = []
    if titulo_html:
        partes.append(f"<h2 style='margin:0 0 4px 0'>{e(item.titulo)}</h2>")
    partes.append(f"<p style='margin:0 0 10px 0'>{e(item.resumo)}</p>")
    if item.quando:
        partes.append(f"<p style='margin:0 0 12px 0'><b>Quando usar:</b> {e(item.quando)}</p>")
    if item.passos:
        partes.append("<h3 style='margin:14px 0 6px 0'>Passo a passo</h3><ol style='margin:0'>")
        for passo in item.passos:
            partes.append(f"<li style='margin-bottom:6px'><b>{e(passo.titulo)}</b><br/>{e(passo.texto)}</li>")
        partes.append("</ol>")
    if item.campos:
        partes.append("<h3 style='margin:14px 0 6px 0'>Campos e colunas</h3>")
        partes.append(
            "<table width='100%' cellspacing='0' cellpadding='5' style='border-collapse:collapse'>"
        )
        for campo in item.campos:
            detalhe = e(campo.o_que_e)
            if campo.como_usar:
                detalhe += f"<br/><i>{e(campo.como_usar)}</i>"
            partes.append(
                f"<tr><td width='32%' valign='top'><b>{e(campo.rotulo)}</b></td>"
                f"<td valign='top'>{detalhe}</td></tr>"
            )
        partes.append("</table>")
    if item.atalhos:
        partes.append("<h3 style='margin:14px 0 6px 0'>Atalhos</h3><ul style='margin:0'>")
        for tecla, descricao in item.atalhos:
            partes.append(f"<li><b>{e(tecla)}</b> — {e(descricao)}</li>")
        partes.append("</ul>")
    if item.cuidados:
        partes.append("<h3 style='margin:14px 0 6px 0'>Atenção</h3><ul style='margin:0'>")
        for cuidado in item.cuidados:
            partes.append(f"<li style='margin-bottom:4px'>{e(cuidado)}</li>")
        partes.append("</ul>")
    if item.relacionados:
        nomes = [POR_CHAVE[chave].titulo for chave in item.relacionados if chave in POR_CHAVE]
        if nomes:
            partes.append(
                f"<p style='margin-top:14px'><b>Ver também:</b> {e(', '.join(nomes))}</p>"
            )
    return "".join(partes)


def guia_em_markdown(*, titulo: str = "Guia de uso do Bússola PDV") -> str:
    """Guia inteiro em Markdown — o que o botão 'Salvar o guia' grava."""
    linhas: list[str] = [f"# {titulo}", ""]
    linhas.append(
        "Gerado pelo próprio programa (Ajuda → Salvar o guia). É o mesmo texto que o "
        "mentor mostra na tela, campo por campo."
    )
    linhas.append("")
    linhas.append("## Sumário")
    for item in GUIA:
        linhas.append(f"- {item.titulo} — {item.resumo}")
    linhas.append("")
    for item in GUIA:
        linhas.append(f"## {item.titulo}")
        linhas.append("")
        linhas.append(item.resumo)
        linhas.append("")
        if item.quando:
            linhas.append(f"**Quando usar:** {item.quando}")
            linhas.append("")
        if item.passos:
            linhas.append("### Passo a passo")
            linhas.append("")
            for indice, passo in enumerate(item.passos, start=1):
                linhas.append(f"{indice}. **{passo.titulo}** — {passo.texto}")
            linhas.append("")
        if item.campos:
            linhas.append("### Campos e colunas")
            linhas.append("")
            linhas.append("| Campo | O que é | Como usar |")
            linhas.append("|---|---|---|")
            for campo in item.campos:
                linhas.append(
                    f"| {campo.rotulo} | {campo.o_que_e} | {campo.como_usar or '—'} |"
                )
            linhas.append("")
        if item.atalhos:
            linhas.append("### Atalhos")
            linhas.append("")
            for tecla, descricao in item.atalhos:
                linhas.append(f"- **{tecla}** — {descricao}")
            linhas.append("")
        if item.cuidados:
            linhas.append("### Atenção")
            linhas.append("")
            for cuidado in item.cuidados:
                linhas.append(f"- {cuidado}")
            linhas.append("")
        if item.relacionados:
            nomes = [POR_CHAVE[chave].titulo for chave in item.relacionados if chave in POR_CHAVE]
            if nomes:
                linhas.append(f"**Ver também:** {', '.join(nomes)}")
                linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


# ------------------------------------------------------------------------- serviço
@dataclass
class ServicoAjuda:
    """Liga/desliga o uso orientado e lembra a versão do guia já apresentada.

    O estado mora na tabela `parametros` (uma linha, sem auditoria — é preferência de
    interface, não regra de negócio). Quem quiser o mentor de volta liga de novo pela
    Ajuda; a escolha sobrevive ao fechamento do programa.

    Sem cache de propósito: o mesmo parâmetro pode ser mudado na tela de Parâmetros
    enquanto o programa roda, e uma preferência que fica velha na memória é daquelas
    que ninguém consegue explicar meses depois. Ler duas linhas do SQLite é barato.
    """

    contexto: Contexto

    # -- estado --------------------------------------------------------------
    def _ler(self, chave: str, padrao: str) -> str:
        try:
            return self.contexto.parametros.obter(chave)
        except Exception:  # pragma: no cover - base antiga sem a chave
            return padrao

    def _gravar(self, chave: str, valor: str) -> None:
        agora = self.contexto.relogio.agora_utc().isoformat()
        self.contexto.parametros.definir(chave, valor, agora_iso=agora)

    def guiado_ativo(self) -> bool:
        return self._ler(CHAVE_GUIADO, "1").strip() in {"1", "true", "True", "S", "SIM"}

    def definir_guiado(self, ativo: bool) -> None:
        self._gravar(CHAVE_GUIADO, "1" if ativo else "0")
        if ativo:
            self._gravar(CHAVE_VERSAO, str(VERSAO_GUIA))

    def versao_vista(self) -> int:
        try:
            return int(self._ler(CHAVE_VERSAO, "0"))
        except ValueError:  # pragma: no cover - valor corrompido no banco
            return 0

    def versao_mudou(self) -> bool:
        """O guia mudou desde a última vez? Serve para reexibir o mentor uma vez."""
        return self.versao_vista() < VERSAO_GUIA

    def reativar(self) -> None:
        """Liga o uso orientado de novo, do primeiro passo."""
        self.definir_guiado(True)

    # -- conteúdo ------------------------------------------------------------
    def temas(self) -> tuple[Tema, ...]:
        return temas()

    def tema(self, chave: str) -> Tema | None:
        return tema(chave)

    def tema_do_modulo(self, modulo: str) -> Tema | None:
        chave = TEMA_DO_MODULO.get(modulo)
        return POR_CHAVE.get(chave) if chave else None

    def buscar(self, texto: str) -> tuple[Tema, ...]:
        return buscar(texto)

    def markdown(self) -> str:
        return guia_em_markdown()

    def salvar_markdown(self, destino: str) -> str:
        from pathlib import Path

        caminho = Path(destino)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(self.markdown(), encoding="utf-8")
        return str(caminho)


__all__ = [
    "CHAVE_GUIADO",
    "CHAVE_VERSAO",
    "GUIA",
    "POR_CHAVE",
    "TEMA_DO_MODULO",
    "VERSAO_GUIA",
    "Campo",
    "Passo",
    "ServicoAjuda",
    "Tema",
    "buscar",
    "guia_em_markdown",
    "tema",
    "tema_em_html",
    "temas",
]
