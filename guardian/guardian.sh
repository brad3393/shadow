#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Guardian Checkpoint Script
#  Creates system snapshots before significant modifications
#  and restores known-safe state when needed.
# ═══════════════════════════════════════════════════════════════

GUARDIAN_DIR="${SHADOW_DATA_DIR:-./shadow_data}/guardian"
CHECKPOINT_DIR="${SHADOW_DATA_DIR:-./shadow_data}/checkpoints"
AUDIT_LOG="$GUARDIAN_DIR/audit.log"

mkdir -p "$CHECKPOINT_DIR" "$GUARDIAN_DIR"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

audit() {
    echo "[$(timestamp)] $1" >> "$AUDIT_LOG"
}

case "$1" in
    checkpoint)
        # Create a checkpoint (snapshot of shadow_data + config)
        CP_ID="cp_$(date +%Y%m%d_%H%M%S)_$$"
        CP_DIR="$CHECKPOINT_DIR/$CP_ID"
        mkdir -p "$CP_DIR"

        # Snapshot the shadow_data directory
        if [ -d "$SHADOW_DATA_DIR" ] || [ -d "./shadow_data" ]; then
            cp -r "${SHADOW_DATA_DIR:-./shadow_data}" "$CP_DIR/data" 2>/dev/null || true
        fi

        # Snapshot config
        cp -r ./config "$CP_DIR/config" 2>/dev/null || true

        # Record metadata
        cat > "$CP_DIR/metadata.json" << META
{
    "id": "$CP_ID",
    "created": "$(timestamp)",
    "reason": "$2",
    "files": $(find "$CP_DIR" -type f | wc -l)
}
META

        audit "CHECKPOINT_CREATED: $CP_ID (reason: $2)"
        echo "$CP_ID"
        ;;

    rollback)
        CP_ID="$2"
        CP_DIR="$CHECKPOINT_DIR/$CP_ID"

        if [ ! -d "$CP_DIR" ]; then
            echo "ERROR: Checkpoint $CP_ID not found" >&2
            audit "ROLLBACK_FAILED: $CP_ID (not found)"
            exit 1
        fi

        # Restore data
        if [ -d "$CP_DIR/data" ]; then
            rm -rf "${SHADOW_DATA_DIR:-./shadow_data}" 2>/dev/null || true
            cp -r "$CP_DIR/data" "${SHADOW_DATA_DIR:-./shadow_data}" 2>/dev/null || true
        fi

        # Restore config
        if [ -d "$CP_DIR/config" ]; then
            rm -rf ./config 2>/dev/null || true
            cp -r "$CP_DIR/config" ./config 2>/dev/null || true
        fi

        audit "ROLLBACK_COMPLETED: $CP_ID"
        echo "Restored from $CP_ID"
        ;;

    list)
        echo "Available checkpoints:"
        for dir in "$CHECKPOINT_DIR"/*; do
            if [ -d "$dir" ]; then
                CP_ID=$(basename "$dir")
                REASON=$(cat "$dir/metadata.json" 2>/dev/null | grep -o '"reason": "[^"]*"' | cut -d'"' -f4)
                CREATED=$(cat "$dir/metadata.json" 2>/dev/null | grep -o '"created": "[^"]*"' | cut -d'"' -f4)
                echo "  $CP_ID  $CREATED  ($REASON)"
            fi
        done
        ;;

    clean)
        # Remove checkpoints older than N days (default 7)
        DAYS="${2:-7}"
        find "$CHECKPOINT_DIR" -maxdepth 1 -type d -mtime +$DAYS -exec rm -rf {} \;
        audit "CHECKPOINTS_CLEANED: older than $DAYS days"
        echo "Cleaned checkpoints older than $DAYS days"
        ;;

    audit)
        echo "=== Guardian Audit Log ==="
        cat "$AUDIT_LOG" 2>/dev/null || echo "(empty)"
        ;;

    *)
        echo "Usage: guardian.sh {checkpoint|rollback|list|clean|audit}"
        echo ""
        echo "  checkpoint [reason]   Create a snapshot"
        echo "  rollback <id>         Restore from snapshot"
        echo "  list                   List all checkpoints"
        echo "  clean [days]           Remove checkpoints older than N days"
        echo "  audit                  Show audit log"
        exit 1
        ;;
esac
