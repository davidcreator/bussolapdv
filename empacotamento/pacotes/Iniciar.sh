#!/bin/sh
# Roda o Bússola PDV direto da pasta extraída, sem instalar nada.
#
# Útil para testar num pendrive ou numa máquina em que você não quer deixar
# vestígio: nada é copiado, nada é registrado. Os dados continuam indo para a
# pasta padrão do sistema (ou para a que você escolher no primeiro uso).
set -eu
AQUI=$(cd "$(dirname "$0")" && pwd)
exec "$AQUI/BussolaPDV/BussolaPDV" "$@"
