#!/bin/sh
# Instala o Bússola PDV para o SEU usuário — sem sudo, sem serviço, sem rede.
#
# O que ele faz, e só isso:
#   1. copia o programa para ~/.local/opt/bussolapdv (ou o caminho de BUSSOLA_DESTINO);
#   2. instala o ícone no tema do seu usuário;
#   3. cria o atalho no menu de aplicativos;
#   4. (se ~/.local/bin existir) deixa o comando `bussolapdv` no PATH.
#
# A base de dados NÃO fica aqui: o programa guarda em ~/.local/share/bussola-pdv
# — ou onde você escolher no primeiro uso, inclusive em outro disco. Desinstalar
# (--remover) apaga o programa, nunca os dados.
#
# Uso:
#   ./Instalar.sh                  instala
#   ./Instalar.sh --remover        remove o programa (mantém a base)
#   BUSSOLA_DESTINO=/opt/pdv ./Instalar.sh   outro destino
set -eu

AQUI=$(cd "$(dirname "$0")" && pwd)
DESTINO="${BUSSOLA_DESTINO:-$HOME/.local/opt/bussolapdv}"
DADOS="${XDG_DATA_HOME:-$HOME/.local/share}"
ATALHOS="$DADOS/applications"
ICONES="$DADOS/icons/hicolor/256x256/apps"
ATALHO="$ATALHOS/bussolapdv.desktop"

remover() {
    if [ -f "$ATALHO" ]; then rm -f "$ATALHO"; echo "Atalho removido: $ATALHO"; fi
    if [ -L "$HOME/.local/bin/bussolapdv" ]; then rm -f "$HOME/.local/bin/bussolapdv"; fi
    if [ -d "$DESTINO" ]; then rm -rf "$DESTINO"; echo "Programa removido: $DESTINO"; fi
    if [ -f "$ICONES/bussolapdv.png" ]; then rm -f "$ICONES/bussolapdv.png"; fi
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$ATALHOS" || true
    echo "Sua base de dados e suas cópias de segurança NÃO foram tocadas."
    exit 0
}

if [ "${1:-}" = "--remover" ]; then
    remover
fi

if [ ! -x "$AQUI/BussolaPDV/BussolaPDV" ]; then
    echo "Não encontrei o programa em $AQUI/BussolaPDV/BussolaPDV" >&2
    echo "Extraia o pacote inteiro antes de rodar este script." >&2
    exit 1
fi

echo "Instalando em $DESTINO ..."
mkdir -p "$DESTINO"
cp -R "$AQUI/BussolaPDV/." "$DESTINO/"
chmod +x "$DESTINO/BussolaPDV"

mkdir -p "$ICONES"
if [ -f "$AQUI/bussola.png" ]; then
    cp "$AQUI/bussola.png" "$ICONES/bussolapdv.png"
else
    echo "Aviso: ícone não encontrado no pacote; o atalho fica sem imagem." >&2
fi

mkdir -p "$ATALHOS"
cat > "$ATALHO" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Bússola PDV
GenericName=Ponto de venda
Comment=PDV offline de código aberto
Exec=$DESTINO/BussolaPDV
Icon=bussolapdv
Terminal=false
Categories=Office;Finance;
StartupWMClass=BussolaPDV
DESKTOP
chmod +x "$ATALHO"

if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$DESTINO/BussolaPDV" "$HOME/.local/bin/bussolapdv"
    echo "Comando: bussolapdv"
fi

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$ATALHOS" || true

echo
echo "Pronto. Abra pelo menu de aplicativos (Bússola PDV) ou rode: $DESTINO/BussolaPDV"
echo "Para remover o programa depois: $AQUI/Instalar.sh --remover"
