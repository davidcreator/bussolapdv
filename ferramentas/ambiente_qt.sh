#!/usr/bin/env bash
# Prepara um ambiente sem root para rodar a interface em modo offscreen e a suíte.
#
# Por que existe: em contêiner/CI sem root não dá para `apt-get install`. Baixamos
# os .deb do Qt com `apt-get download` e extraímos em /tmp/libs, apontando
# LD_LIBRARY_PATH. Idempotente: pode rodar quantas vezes quiser.
#
# Uso:  source ferramentas/ambiente_qt.sh    # exporta as variáveis no shell atual
#       bash ferramentas/ambiente_qt.sh      # apenas prepara os arquivos
set -u

DESTINO_LIBS="${DESTINO_LIBS:-/tmp/libs}"
DESTINO_DEBS="${DESTINO_DEBS:-/tmp/debs}"
PACOTES="
libxkbcommon0 libxkbcommon-x11-0 libgl1 libglvnd0 libegl1 libfontconfig1 libfreetype6
libpng16-16t64 libexpat1 libbrotli1 libgraphite2-3 libharfbuzz0b libglib2.0-0t64
libpcre2-8-0 libdbus-1-3 libx11-xcb1 libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0
libxcb-keysyms1 libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0 libxcb-shm0
libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xkb1 libxcb-glx0 libsm6 libice6 libxi6
libxtst6 libxrender1 libdouble-conversion3 libminizip1t64 libbz2-1.0 libzstd1 liblzma5
libuuid1 libmd0
"

if [ ! -d "$DESTINO_LIBS/usr/lib/x86_64-linux-gnu" ]; then
    mkdir -p "$DESTINO_DEBS" "$DESTINO_LIBS"
    if command -v apt-get >/dev/null 2>&1; then
        ( cd "$DESTINO_DEBS" || exit 1
          for pacote in $PACOTES; do
              apt-get download "$pacote" >/dev/null 2>&1 || echo "aviso: sem pacote $pacote"
          done
        )
        for deb in "$DESTINO_DEBS"/*.deb; do
            [ -e "$deb" ] || continue
            dpkg-deb -x "$deb" "$DESTINO_LIBS" 2>/dev/null
        done
    else
        echo "apt-get indisponível: instale as bibliotecas do Qt pelo gerenciador do sistema." >&2
    fi
fi

export LD_LIBRARY_PATH="$DESTINO_LIBS/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export PYTHONPATH="src:${PYTHONPATH:-}"

if python3 -c "from PySide6.QtWidgets import QApplication" 2>/dev/null; then
    echo "Qt offscreen pronto (LD_LIBRARY_PATH=$LD_LIBRARY_PATH)"
else
    echo "Qt ainda indisponível: instale as dependências Python com 'pip install -e .[dev]'." >&2
    exit 1
fi
