#!/bin/sh
# Restore hive persistent data
# Usage: ./scripts/restore.sh <backup.tar.gz> [target]
# target: host (default, restores ~/.hive) or volume name (e.g., hive-research-cli_hive_data)

set -e
BACKUP=${1:-}
TARGET=${2:-host}

if [ -z "$BACKUP" ]; then
  echo "Usage: $0 <backup.tar.gz> [host|volume_name]"
  echo "  host: restores ~/.hive (default)"
  echo "  volume: e.g., hive-research-cli_hive_data"
  exit 1
fi

if [ "$TARGET" = "host" ]; then
  echo "→ Restoring $BACKUP → ~/.hive (will overwrite)"
  mkdir -p "$HOME/.hive"
  tar xzf "$BACKUP" -C "$HOME" --strip-components=1 2>/dev/null || tar xzf "$BACKUP" -C "$HOME/.hive" --strip-components=1
  echo "→ Restored to $HOME/.hive — ls:"
  ls -lh "$HOME/.hive" | head -n 20
else
  echo "→ Restoring $BACKUP → volume $TARGET"
  docker volume create "$TARGET" >/dev/null 2>&1 || true
  docker run --rm -v "$TARGET":/volume -v "$(pwd)":/backup alpine sh -c "rm -rf /volume/* && tar xzf /backup/$BACKUP -C /volume --strip-components=1 2>/dev/null || tar xzf /backup/$BACKUP -C /volume"
  echo "→ Restored volume $TARGET"
fi
