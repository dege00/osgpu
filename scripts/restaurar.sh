#!/usr/bin/env bash
#
# Restaura um backup do Assistec. Por padrão restaura em um banco e um volume
# de TESTE (não toca em produção). Para sobrescrever produção é preciso passar
# --producao e digitar CONFIRMAR.
#
# Uso:
#   ./scripts/restaurar.sh <arquivo-banco.sql.gz> <arquivo-media.tar.gz>
#   ./scripts/restaurar.sh --producao <arquivo-banco.sql.gz> <arquivo-media.tar.gz>
#
# Variáveis (opcionais):
#   COMPOSE_PROJECT_NAME  nome do projeto compose (padrão: assistec)
#   POSTGRES_USER         usuário do banco        (padrão: assistec)
#   POSTGRES_DB           banco de produção       (padrão: assistec)
#   BANCO_TESTE           banco de teste          (padrão: assistec_restore)
#   VOLUME_MEDIA          volume de produção      (padrão: assistec_media; o compose fixa "name: assistec")
#   VOLUME_MEDIA_TESTE    volume de teste         (padrão: assistec_media_restore)
#   IMAGEM_HELPER         imagem para o tar       (padrão: alpine:3)
set -euo pipefail

PROJETO="assistec"
POSTGRES_USER="${POSTGRES_USER:-assistec}"
BANCO_PRODUCAO="${POSTGRES_DB:-assistec}"
VOLUME_MEDIA_PRODUCAO="${VOLUME_MEDIA:-${PROJETO}_media}"
BANCO_TESTE="${BANCO_TESTE:-assistec_restore}"
VOLUME_MEDIA_TESTE="${VOLUME_MEDIA_TESTE:-${PROJETO}_media_restore}"
IMAGEM_HELPER="${IMAGEM_HELPER:-alpine:3}"

PRODUCAO=0
if [ "${1:-}" = "--producao" ]; then
  PRODUCAO=1
  shift
fi

ARQUIVO_BANCO="${1:-}"
ARQUIVO_MEDIA="${2:-}"

if [ -z "$ARQUIVO_BANCO" ] || [ -z "$ARQUIVO_MEDIA" ]; then
  echo "uso: $0 [--producao] <arquivo-banco.sql.gz> <arquivo-media.tar.gz>" >&2
  exit 2
fi
[ -f "$ARQUIVO_BANCO" ] || { echo "erro: $ARQUIVO_BANCO não existe" >&2; exit 1; }
[ -f "$ARQUIVO_MEDIA" ] || { echo "erro: $ARQUIVO_MEDIA não existe" >&2; exit 1; }

# Valida os arquivos ANTES de qualquer ação destrutiva (parar backend, dropdb, limpar volume).
echo "[restore] validando os arquivos de backup"
gzip -t "$ARQUIVO_BANCO" || { echo "erro: $ARQUIVO_BANCO não é um gzip válido (arquivo corrompido/incompleto)" >&2; exit 1; }
tar tzf "$ARQUIVO_MEDIA" >/dev/null || { echo "erro: $ARQUIVO_MEDIA não é um tar.gz válido (arquivo corrompido/incompleto)" >&2; exit 1; }

cd "$(dirname "$0")/.."

if [ "$PRODUCAO" = "1" ]; then
  ALVO_BANCO="$BANCO_PRODUCAO"
  ALVO_MEDIA="$VOLUME_MEDIA_PRODUCAO"
  echo "ATENÇÃO: restauração em PRODUÇÃO."
  echo "O banco '$ALVO_BANCO' e o volume '$ALVO_MEDIA' serão SOBRESCRITOS."
  read -r -p "Digite exatamente CONFIRMAR para continuar: " resposta
  [ "$resposta" = "CONFIRMAR" ] || { echo "cancelado pelo usuário."; exit 1; }
  echo "[restore] guardando o estado atual antes de sobrescrever (backup.sh)"
  ./scripts/backup.sh
  echo "[restore] parando o backend para liberar o banco"
  docker compose stop backend
  trap 'echo "A restauração falhou. O backend continua PARADO. O estado anterior foi salvo pelo backup.sh feito antes (veja o diretório de backup). Corrija o problema e rode de novo, ou religue com: docker compose start backend" >&2' ERR
else
  ALVO_BANCO="$BANCO_TESTE"
  ALVO_MEDIA="$VOLUME_MEDIA_TESTE"
  echo "[restore] modo teste: banco '$ALVO_BANCO' e volume '$ALVO_MEDIA'"
fi

echo "[restore] $(date -Is) restaurando banco em '$ALVO_BANCO'"
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -q -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$ALVO_BANCO' AND pid<>pg_backend_pid();"
docker compose exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$ALVO_BANCO"
docker compose exec -T db createdb -U "$POSTGRES_USER" "$ALVO_BANCO"
gunzip -c "$ARQUIVO_BANCO" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$ALVO_BANCO" -q -v ON_ERROR_STOP=1 --single-transaction

echo "[restore] $(date -Is) validando arquivo de mídia '$ARQUIVO_MEDIA'"
tar tzf "$ARQUIVO_MEDIA" >/dev/null

echo "[restore] $(date -Is) restaurando mídia no volume '$ALVO_MEDIA'"
DIR_MEDIA="$(cd "$(dirname "$ARQUIVO_MEDIA")" && pwd)"
NOME_MEDIA="$(basename "$ARQUIVO_MEDIA")"
docker volume create "$ALVO_MEDIA" >/dev/null
docker run --rm \
  -v "${ALVO_MEDIA}:/media" \
  -v "${DIR_MEDIA}:/backup:ro" \
  "$IMAGEM_HELPER" sh -c \
  'find /media -mindepth 1 -delete; tar xzf "/backup/'"$NOME_MEDIA"'" -C /media'

if [ "$PRODUCAO" = "1" ]; then
  echo "[restore] religando o backend"
  docker compose start backend
fi

echo "[restore] $(date -Is) contagens no banco restaurado ($ALVO_BANCO):"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$ALVO_BANCO" -c \
  "SELECT 'lojas' AS tabela, count(*) FROM core_loja
   UNION ALL SELECT 'clientes', count(*) FROM core_cliente
   UNION ALL SELECT 'pecas', count(*) FROM core_peca
   UNION ALL SELECT 'ordens', count(*) FROM core_ordemservico
   UNION ALL SELECT 'fotos', count(*) FROM core_fotoos;"

echo "[restore] $(date -Is) concluído"
