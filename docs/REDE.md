# Vários caixas na mesma base (rede)

> **Status na v0.15.0:** funcionam **os dois lados**. O servidor (ADR-035) tem API,
> TLS gerado pelo programa, identidade de terminal, log de acesso e teste de dois
> caixas vendendo ao mesmo tempo; e o **caixa agora é cliente de verdade**
> (ADR-036): a janela inteira — PDV, caixa, cadastros, consultas, crediário,
> devolução, estoque, relatórios e administração — roda contra o servidor, com
> configuração no primeiro uso, digital do certificado fixada e **fila offline**
> para a venda quando a rede cai. O que falta é operação em loja real e os itens
> de robustez da seção 4.

## 1. Por que não "SQLite numa pasta de rede"

O caminho mais óbvio (e o mais errado) é compartilhar `bussola.db` numa pasta de rede
e abrir o mesmo arquivo de dois computadores. Não funciona:

- o bloqueio de escrita do SQLite (`-wal`, `-shm`) depende do **sistema de arquivos**;
  SMB/NFS não garantem as travas — o resultado é corrupção silenciosa, não erro;
- duas estações gravando a mesma venda, o mesmo turno e o mesmo número sequencial
  geram duplicidade que a auditoria detecta **depois** do estrago;
- qualquer queda de rede no meio de uma transação deixa o arquivo em estado ambíguo.

O programa avisa isso no README e no manual. Não é limitação temporária: é
propriedade do modelo de arquivo.

## 2. Arquitetura escolhida: servidor central + terminais

```
┌────────────────────┐    HTTPS + token + X-Bussola-Terminal   ┌──────────────────────────┐
│ Terminal do balcão │ ───────────────────────────────────────▶ │  Servidor (uma máquina)  │
│  (cliente HTTP)    │ ◀─────────────────────────────────────── │  API TLS + bussola.db    │
└────────────────────┘                                          └──────────────────────────┘
┌────────────────────┐                                                     │
│ Segundo terminal   │ ────────────────────────────────────────────────────┘
└────────────────────┘                            backup local + cópia na nuvem
```

- **uma base só**, no servidor — a fonte da verdade é única, como hoje;
- cada terminal é **cliente**: a tela continua igual, o que muda é onde a operação é
  executada;
- o servidor pode ser a máquina do escritório da ONG, uma VM na AWS/Azure
  (`docs/NUVEM.md`) ou um mini-PC na loja;
- se a rede cair no meio de uma venda, a venda **fica guardada no caixa** e é
  reenviada quando o servidor voltar (ADR-036). Não existe base paralela: o que a
  fila guarda é a *solicitação de venda*, com a mesma `chave_idempotencia`, e o
  servidor não registra duas vezes.

## 3. O que já existe (v0.14.0)

| Peça | Estado |
|---|---|
| Rotas de leitura (produtos, estoque, vendas, crediário, turnos, devoluções, relatórios) | ✅ |
| **Rotas de escrita**: venda, abrir/fechar turno, receber título (com encargo), entrada de estoque, devolução, cancelamento | ✅ |
| Token por aplicativo + login/senha por operação (e autorizador quando a regra pede) | ✅ |
| **TLS embutido**: certificado autoassinado gerado pelo programa (`--tls`), sem OpenSSL nem SDK | ✅ |
| Recusa de `--host` de rede sem TLS | ✅ (falha na subida, não vira HTTP aberto) |
| **Identidade de terminal**: `X-Bussola-Terminal` → `vendas.terminal_id`, `turnos.terminal_id` | ✅ (migração 0006) |
| **Log de acesso** JSONL (quando, terminal, IP, rota, status, ms) | ✅ |
| Contexto por thread (conexão SQLite nunca atravessa thread) | ✅ |
| **Teste de concorrência**: dois terminais disputando o último item | ✅ |

### O caixa como cliente (v0.15.0)

O modo é decidido **pelo computador**: existe `terminal.json` na pasta de dados?
Então esta máquina é terminal e abre sem base local. Não existe a escolha pelo
operador — quem instala não pode errar no meio do expediente.

```powershell
# do lado do caixa, uma vez: pede endereço, token, nome do caixa e mostra a digital
python -m bussola_pdv terminal configurar
python -m bussola_pdv terminal status      # a que servidor está ligado, fila pendente
python -m bussola_pdv terminal testar      # servidor respondeu? digital confere?
python -m bussola_pdv terminal local       # desliga o modo terminal nesta máquina
```

Na tela, o mesmo caminho é o botão **"Este caixa usa um servidor…"** da tela de
login (que só aparece quando a máquina ainda é local).

| Peça | Como funciona |
|---|---|
| Chamada de serviço | `POST /v1/executar {servico, metodo, argumentos}` — **um** executor, lista fechada de serviços |
| Contrato | a assinatura do método do serviço é o contrato; tipos de fronteira viajam como inteiros |
| Identidade | o servidor **descarta** o ator enviado e usa o usuário da sessão |
| Login | senha conferida no servidor → `token_sessao`; a senha não fica no caixa |
| Autorizador (desconto, sangria) | senha do gerente no servidor → credencial de 5 min, uso único |
| Certificado | SHA-256 mostrado no primeiro uso, confirmado pelo operador e **fixado** em `servidor-do-caixa.crt` |
| Queda de rede | venda vai para `vendas-pendentes.db`, tela limpa o carrinho, menu **Vendas pendentes** reenvia |
| Impressão | documento montado no servidor, papel no caixa |
| Relatórios | gerados no servidor, baixados para a pasta do operador |
| Manutenção | cópia/restauração/pasta de dados são do **servidor** — a tela do terminal diz isso |
| Cargas pendentes | `terminal.json`, `servidor-do-caixa.crt` e `vendas-pendentes.db` na pasta de dados do caixa |

O que a fila **não** faz: não guarda venda de retirada sem estoque, não decide
preço pelo servidor no reenvio (a venda guardada mantém o preço que o cliente
pagou) e não reenvia sozinha no meio do expediente — reenviar é ato do operador
que fez a venda, na tela de pendências.

### Como subir o servidor hoje

```powershell
# Windows, base em D:\pdv
set BUSSOLA_API_TOKEN=token-longo-e-aleatorio
"D:\Program Files\Python314\python.exe" -m bussola_pdv.cli api `
    --banco D:\pdv\bussola.db --host 0.0.0.0 --porta 8765 --tls --terminal SERVIDOR
```

A saída mostra o endereço `https://…`, o caminho do certificado e a **impressão
digital SHA-256**. O terminal confere essa impressão (por telefone ou olhando a tela
do servidor) antes de confiar no certificado — é o que substitui a autoridade
certificadora numa rede local. O certificado é gerado uma vez em `<dados>\tls` e
reaproveitado nas subidas seguintes.

## 4. O que falta, em ordem

1. ~~**Tela cliente (modo terminal)**~~ — feito na v0.15.0 (ADR-036), janela
   completa, não só PDV.
2. ~~**Fila offline do terminal**~~ — feito na v0.15.0: a venda é guardada com
   `chave_idempotencia` e reenviada; recusa de negócio vira pendência com motivo.
3. ~~**Confiança do certificado no Windows**~~ — resolvido sem instalar `.crt`:
   o terminal fixa a digital no primeiro uso e recusa outra. Instalar o
   certificado como autoridade deixou de ser requisito.
4. **Token por terminal** — hoje um token serve todos; com vários caixas, um token
   por máquina permite revogar um terminal perdido sem derrubar os outros.
5. **Fechamento por terminal** — `turnos.terminal_id` já grava; falta o relatório
   "quanto cada caixa fez", que é o que a loja confere de manhã.
6. **Teste de carga** — 10 terminais simultâneos, medindo latência de venda. O
   SQLite em WAL aguenta bem o volume de um bazar, mas isso precisa de número, não
   de opinião.
7. **Reenvio automático da fila** — hoje é botão na tela de pendências. Automático
   (a cada N minutos, ou quando a conexão volta) é melhoria, não requisito: quem
   reenvia precisa estar logado, e a venda é do operador que a fez.

## 5. Alternativa descartada por ora: réplica por caixa

Cada caixa com SQLite próprio, sincronizando eventos quando há rede. Funciona com
internet instável, mas custa caro: conflito de estoque, resolução de duplicidade,
relógios diferentes e o mesmo problema de "dois donos do número da venda". Só entra
se a loja tiver **rede instável e vendas simultâneas** — e, nesse caso, a decisão tem
que ser tomada antes, porque muda o modelo de dados.

## 6. Segurança mínima para ligar em rede

- TLS obrigatório — hoje o próprio comando recusa host de rede sem `--tls`;
- um token por terminal, guardado em variável de ambiente da máquina;
- firewall liberando **só** a porta da API, e só para a faixa da loja;
- log de acesso ligado (padrão do comando em modo servidor);
- backup do servidor: local **e** na nuvem (`docs/NUVEM.md`), com restauração testada.

## 7. O que a concorrência faz hoje (e o que ela não faz)

O teste `tests/test_rede_multi_caixa.py` prova o comportamento real:

- **duas vendas do mesmo último item ao mesmo tempo**: uma passa, a outra é recusada
  com mensagem de estoque — não existe estoque negativo silencioso;
- **venda com estoque negativo autorizada** continua sendo possível, mas só por quem
  tem a permissão `PDV_VENDA_ESTOQUE_NEGATIVO` (gerente/admin) e com aviso na
  resposta — é a regra do programa, não um acidente da rede;
- **leituras simultâneas** em threads diferentes não compartilham conexão (cada
  thread abre a sua), então não há corrupção nem bloqueio cruzado.

O que **não** está provado: comportamento com disco lento, rede saturada e 10+
terminais simultâneos (item 6 da lista acima).

## 8. O certificado em si tem teste próprio

`tests/test_certificado.py` (22) não confia no arquivo: **reparseia o DER** e confere

- série **positiva** e diferente a cada geração (série negativa é recusada por
  validador estrito);
- `Name` com RDN em **SET (0x31)** — com SEQUENCE o OpenSSL só diz "PEM lib";
- `subjectAltName` com `localhost`, `127.0.0.1` e o IP local, senão o terminal
  recusa o servidor pelo nome;
- **assinatura RSA conferida matematicamente** (`pow(s, e, n)` com PKCS#1 v1.5),
  não só "o arquivo abre";
- chave privada com permissão `0600` fora do Windows;
- `obter_ou_criar` **reaproveita** o par (regerar trocaria a digital e obrigaria a
  reconfigurar todos os caixas).

O teste achou um defeito real no gerador: `der_inteiro` descartava o byte de sinal e
um inteiro com o bit alto ligado saía **negativo** em DER. Não atingia a série (119
bits, sempre positiva), mas atingiria qualquer campo novo.
