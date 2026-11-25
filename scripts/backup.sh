#!/usr/bin/env bash
#
# Backup do Assistec: dump comprimido do PostgreSQL + tar.gz do volume de mídia.
# Deve rodar na raiz do projeto (onde está o docker-compose.yml).
#
# Uso:
#   ./scripts/backup.sh
#
# Variáveis (opcionais):
#   DIRETORIO_BACKUP      destino local           (padrão: /var/backups/assistec)
#   DIAS_RETENCAO         dias de retenção        (padrão: 14)
#   COMPOSE_PROJECT_NAME  nome do projeto compose (padrão: assistec)
#   POSTGRES_USER         usuário do banco        (padrão: assistec)
#   POSTGRES_DB           nome do banco           (padrão: assistec)
#   VOLUME_MEDIA          volume da mídia         (padrão: assistec_media; o compose fixa "name: assistec")
#   IMAGEM_HELPER         imagem para o tar       (padrão: alpine:3)
set -euo pipefail
umask 077   # só o dono lê/escreve o que este script criar

DIRETORIO_BACKUP="${DIRETORIO_BACKUP:-/var/backups/assistec}"
DIAS_RETENCAO="${DIAS_RETENCAO:-14}"
PROJETO="assistec"
POSTGRES_USER="${POSTGRES_USER:-assistec}"
POSTGRES_DB="${POSTGRES_DB:-assistec}"
VOLUME_MEDIA="${VOLUME_MEDIA:-${PROJETO}_media}"
IMAGEM_HELPER="${IMAGEM_HELPER:-alpine:3}"

cd "$(dirname "$0")/.."

DATA="$(date +%F-%H%M)"
BANCO="$DIRETORIO_BACKUP/banco-$DATA.sql.gz"
MEDIA="$DIRETORIO_BACKUP/media-$DATA.tar.gz"
BANCO_TMP="$BANCO.tmp"
MEDIA_TMP="$MEDIA.tmp"

# Em qualquer saída (erro ou sucesso) remove os parciais; no sucesso eles já
# viraram o arquivo final, então o rm é inofensivo.
trap 'rm -f "$BANCO_TMP" "$MEDIA_TMP"' EXIT

mkdir -p "$DIRETORIO_BACKUP"
chmod 700 "$DIRETORIO_BACKUP"   # pasta de backup restrita ao dono

echo "[backup] $(date -Is) dump do banco -> $BANCO"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BANCO_TMP"
gzip -t "$BANCO_TMP"          # falha se o dump saiu corrompido/incompleto

echo "[backup] $(date -Is) mídia (volume $VOLUME_MEDIA) -> $MEDIA"
if ! docker volume inspect "$VOLUME_MEDIA" >/dev/null 2>&1; then
  echo "erro: o volume '$VOLUME_MEDIA' não existe. Suba o sistema (docker compose up -d) antes de fazer backup." >&2
  exit 1
fi
if [ -z "$(docker run --rm -v "${VOLUME_MEDIA}:/media:ro" "$IMAGEM_HELPER" sh -c 'find /media -mindepth 1 -print -quit')" ]; then
  echo "[backup] aviso: o volume '$VOLUME_MEDIA' está vazio (nenhuma foto será salva)." >&2
fi
docker run --rm \
  -v "${VOLUME_MEDIA}:/media:ro" \
  -v "${DIRETORIO_BACKUP}:/backup" \
  "$IMAGEM_HELPER" \
  tar czf "/backup/media-$DATA.tar.gz.tmp" -C /media .
tar tzf "$MEDIA_TMP" >/dev/null  # valida o arquivo gerado

echo "[backup] $(date -Is) publicando o par banco + mídia"
mv "$BANCO_TMP" "$BANCO"
mv "$MEDIA_TMP" "$MEDIA"

echo "[backup] $(date -Is) removendo arquivos com mais de $DIAS_RETENCAO dias"
find "$DIRETORIO_BACKUP" -type f \( -name 'banco-*.sql.gz' -o -name 'media-*.tar.gz' \) -mtime +"$DIAS_RETENCAO" -delete

echo "[backup] $(date -Is) concluído"
ls -lh "$BANCO" "$MEDIA"
