# Backup e reinstalação — não perder os dados

A base do Bússola PDV é **um arquivo**: `pdv.db`, dentro da pasta de dados. Tudo
o que importa está nele — vendas, itens, pagamentos, clientes, crediário,
estoque, usuários, auditoria e a marca da loja. Relatórios exportados, cópias e
logs são derivados e ficam nas pastas ao lado.

> **A regra que vale acima de todas:** uma base sem cópia é uma base sem volta.
> Nenhum procedimento deste documento substitui ter a cópia **fora do
> computador** (pen drive, HD externo, armazenamento em nuvem da loja).

---

## Onde ficam os dados

| O quê | Onde (Windows) | Precisa de backup? |
| --- | --- | --- |
| Base | `<pasta de dados>\pdv.db` | **sim, é o que importa** |
| Cópias de segurança | `<pasta de dados>\copias\` | sim, mas é o próprio backup |
| Relatórios exportados | `<pasta de dados>\relatorios\` | opcional (dá para reemitir) |
| Logs de erro | `<pasta de dados>\logs\` | só para suporte |
| Ponteiro da instalação | `%APPDATA%\BussolaPDV\instalacao.json` | não (é só o caminho) |

A pasta de dados padrão é `%LOCALAPPDATA%\BussolaPDV`, mas **quem instala escolhe
outra** na tela de primeiro uso (por exemplo `D:\pdv`). Para saber qual está em
uso:

```bat
bussola dados --mostrar
```

O programa nunca grava dados dentro da pasta de instalação. Por isso
**desinstalar e reinstalar não apaga a base** — desde que a pasta de dados não
seja apagada à mão.

---

## Três jeitos de fazer a cópia (use os três)

### 1. Automático, todo dia, sem ninguém lembrar

Toda vez que o programa abre, `ServicoBackup.automatico()` cria **uma cópia por
dia** em `<pasta de dados>\copias\` e mantém as **14 últimas**. Cópia automática
antiga é apagada; **cópia manual nunca é apagada pelo programa**.

Cada cópia leva um manifesto ao lado (`pdv-AAAAMMDD-HHMMSS.db.manifesto.json`)
com data, versão do programa, versão do esquema, **contagem de registros** e
`sha256`. É texto simples, legível sem o programa — de propósito.

Se a cópia falhar (disco cheio, pasta sem permissão), a loja abre normalmente e
o motivo vai para `logs/erros.log`. Backup não impede vender; mas o aviso não
pode ser ignorado.

### 2. Manual, pela interface (antes de mexer em algo)

**Administração › Manutenção**:

- **Gerar cópia agora** — cópia verificada na pasta escolhida;
- **Criar cópia automática agora** — força a cópia do dia;
- **Verificar cópia selecionada** / **Verificar arquivo…** — abre a cópia em modo
  somente leitura e roda `PRAGMA integrity_check` + confere as tabelas do PDV;
- **Restaurar selecionada…** — substitui a base atual e guarda a anterior como
  `pdv.db.antes-de-restaurar-<data>` (só Admin Master).

### 3. Fora do programa, quando ele não abre

É o caso que mais dói: a base corrompeu, a atualização parou no meio, o Python
quebrou. A ferramenta `Backup\backup_externo.py` (instalada junto com o
programa) **não importa o pacote `bussola_pdv`** — usa só a biblioteca padrão do
Python — e faz tudo o que o programa faz:

```bat
Backup\backup_externo.bat                :: cria a cópia do dia (duplo clique também)
Backup\backup_externo.bat listar         :: mostra as cópias, tamanho e integridade
Backup\backup_externo.bat verificar ARQ  :: confere um arquivo antes de confiar
Backup\backup_externo.bat restaurar ARQ  :: devolve a cópia (feche o PDV antes!)
Backup\backup_externo.bat recuperar      :: tenta salvar uma base danificada
```

Opções: `--pasta CAMINHO` (pasta de dados) e `--destino PASTA` (onde gravar).

Rodando do código-fonte: `python ferramentas/backup_externo.py listar`.

**Se nem o Python existir na máquina** (instalação removida, por exemplo), o
último recurso é o mais simples: feche o PDV e copie a pasta de dados inteira
para um pen drive. O arquivo que importa é o `pdv.db` — com ele em mãos, o
programa pode ser reinstalado e a base devolvida no lugar.

---

## Recuperar uma base danificada

1. **Pare de usar o arquivo.** Cada abertura escreve nele; quanto mais tentativas
   com a base corrompida, menos dado sobra.
2. Faça uma cópia crua do `.db` (mesmo corrompido) para investigação.
3. Tente a recuperação, que salva o que der para ler:

   ```bat
   Backup\backup_externo.bat recuperar --pasta C:\caminho\da\pasta
   ```

   O resultado é `pdv-recuperado.db`. Ele **não promete** recuperação total: usa
   `iterdump()`, que lê página por página e descarta o que não consegue ler.
4. Confira antes de usar:

   ```bat
   Backup\backup_externo.bat verificar pdv-recuperado.db
   ```

5. Se o resultado não servir, restaure a **cópia de segurança mais recente que
   passar na verificação**.

---

## Reinstalar o programa sem perder nada

Checklist, na ordem:

1. **Cópia primeiro.** `Backup\backup_externo.bat` (ou Administração ›
   Manutenção › Gerar cópia agora). Confirme que a cópia está "íntegra".
2. **Copie a cópia para fora da máquina** (pen drive). Reinstalar não apaga a
   base, mas uma falha de disco apaga.
3. Anote a pasta de dados em uso: `bussola dados --mostrar`
   (ex.: `D:\pdv`).
4. Desinstale/reinstale normalmente. O instalador **não** toca em
   `%LOCALAPPDATA%\BussolaPDV` nem na pasta de dados escolhida.
5. Abra o programa. Se ele não encontrar a base que você esperava, aponte a pasta
   certa em **Administração › Manutenção › Alterar pasta dos dados…** (ou no
   primeiro uso, no campo *Pasta dos dados*).
6. Confira: **Vendas** do dia, **Fechamento do dia** e o total de produtos.
   Só então volte a vender.

Se estiver migrando para outro computador:

1. no antigo: cópia verificada + copie o `.db` para o pen drive;
2. no novo: instale, abra, **não** passe pelo primeiro uso criando base nova —
   escolha a pasta de dados que contém o `pdv.db` trazido;
3. se o primeiro uso já tiver criado uma base, use
   **Manutenção › Restaurar selecionada…** apontando a cópia trazida.

---

## O que o manifesto contém

```json
{
  "arquivo": "pdv-20261111-143800.db",
  "rotulo": "manual",
  "automatico": false,
  "criado_em_utc": "2026-11-11T17:38:00+00:00",
  "versao_aplicativo": "0.9.0",
  "versao_esquema": 3,
  "bytes": 401408,
  "sha256": "…",
  "contagens": {"produtos": 16, "vendas": 16, "itens_venda": 27, "usuarios": 5},
  "integro": true,
  "formato": 1,
  "como_restaurar": "Feche o Bússola PDV, guarde o pdv.db atual e copie este arquivo para pdv.db …"
}
```

Serve para responder, sem abrir o programa: *quando* foi feita, *de que versão*,
*quantos registros* tem e *se o arquivo é o mesmo* (`sha256`).

---

## Limites (o que este recurso **não** faz)

- **Não** replica a base para fora da máquina. Backup na mesma máquina protege
  contra erro humano e corrupção, **não** contra roubo, incêndio ou disco morto.
- **Não** substitui restauração automática: restaurar é decisão explícita, do
  Admin Master.
- **Não** é backup incremental: cada cópia é o arquivo inteiro (uma base de PDV
  de loja pequena tem poucos MB, o custo é irrelevante).
- **Não** foi exercitado em Windows real nesta versão: a suíte roda a ferramenta
  em processo separado **no Linux**, incluindo criar, listar, verificar,
  restaurar e recuperar. O `.bat` não é coberto por teste automatizado.
