#!/bin/sh
# Roda o Bússola PDV no macOS sem instalar (duplo clique no Finder).
#
# O macOS bloqueia programas baixados da internet sem assinatura: se aparecer
# "não pode ser aberto", clique com o botão direito no arquivo > Abrir > Abrir.
set -eu
AQUI=$(cd "$(dirname "$0")" && pwd)
exec "$AQUI/BussolaPDV.app/Contents/MacOS/BussolaPDV" "$@"
