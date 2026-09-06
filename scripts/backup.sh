#!/bin/sh
# Backup hive persistent data (host ~/.hive + volumes) — rebuild-safe
# Usage: ./scripts/backup.sh [backup_dir]
# Creates tar.gz of ~/.hive and docker volumes hive_data, ollama_data, open_webui_data

set -e
BACKUP_DIR=${1:-./backups}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"

echo "→ Backing up host ~/.hive → $BACKUP_DIR/hive-host-$TIMESTAMP.tar.gz"
tar czf "$BACKUP_DIR/hive-host-$TIMESTAMP.tar.gz" -C "$HOME" .hive 2>/dev/null || echo "  (no ~/.hive yet)"

for vol in hive_data ollama_data open_webui_data; do
  # docker compose volume name is typically <project>_<vol> — try both
  for v in "hive-research-cli_${vol}" "$vol" "hive-research_${vol}"; do
    if docker volume inspect "$v" >/dev/null 2>&1; then
      echo "→ Backing up volume $v → $BACKUP_DIR/${v}-$TIMESTAMP.tar.gz"
      docker run --rm -v "$v":/volume -v "$(pwd)/$BACKUP_DIR":/backup alpine tar czf "/backup/${v}-$TIMESTAMP.tar.gz" -C /volume .
      break
    fi
  done
done

echo "→ Backup complete: ls -lh $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -n 20
echo "Restore: ./scripts/restore.sh $BACKUP_DIR/hive-host-$TIMESTAMP.tar.gz"
echo "Note: docker compose down (without -v) keeps volumes; down -v deletes them — restore from backup then."
