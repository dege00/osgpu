#!/usr/bin/env bash
#
# Envia os backups para fora da VPS com rclone, usando um remoto CRIPTOGRAFADO
# (crypt) sobre o bucket. Os arquivos saem cifrados: sem a senha e o salt do
# crypt, o conteúdo no bucket é ilegível. Veja em docs/DEPLOY.md como criar o
# remoto crypt e onde guardar essas senhas.
#
# Uso:
#   RCLONE_DESTINO="cript:assistec" ./scripts/enviar_backup.sh
#
# Variáveis (opcionais):
#   DIRETORIO_BACKUP  origem local   (padrão: /var/backups/assistec)
#   RCLONE_CONFIG     arquivo conf   (padrão: /etc/rclone/rclone.conf)
set -euo pipefail

DIRETORIO_BACKUP="${DIRETORIO_BACKUP:-/var/backups/assistec}"
RCLONE_DESTINO="${RCLONE_DESTINO:-}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/etc/rclone/rclone.conf}"

if [ -z "$RCLONE_DESTINO" ]; then
  echo "erro: defina RCLONE_DESTINO com o remoto criptografado (ex.: cript:assistec)" >&2
  exit 1
fi
if ! command -v rclone >/dev/null 2>&1; then
  echo "erro: rclone não está instalado (veja docs/DEPLOY.md)" >&2
  exit 1
fi
if [ ! -f "$RCLONE_CONFIG" ]; then
  echo "erro: não encontrei o rclone.conf em $RCLONE_CONFIG (veja docs/DEPLOY.md)" >&2
  exit 1
fi

echo "[envio] $(date -Is) copiando backups novos para $RCLONE_DESTINO"
rclone --config "$RCLONE_CONFIG" copy "$DIRETORIO_BACKUP" "$RCLONE_DESTINO" \
  --include "*.sql.gz" --include "*.tar.gz" \
  --transfers 2 --checkers 4 --log-level INFO

echo "[envio] $(date -Is) concluído"
