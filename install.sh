#!/bin/bash
# Symlink every skill in this repo into the agent skill directories.
# Usage: ./install.sh [--dry-run] [--force]
#   --dry-run  show what would change, change nothing
#   --force    move differing local copies to ~/.agents/skills-backup/<timestamp>/ and link anyway
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DRY_RUN=0
FORCE=0
for ARG in "$@"; do
    case "$ARG" in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    -h | --help)
        sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    *)
        echo "Unknown option: $ARG" >&2
        exit 1
        ;;
    esac
done

# ~/.agents/skills is read by pi, DSH and other Agent Skills clients.
# Claude Code only reads ~/.claude/skills, so link there too when Claude is installed.
TARGETS=("$HOME/.agents/skills")
[[ -d "$HOME/.claude" ]] && TARGETS+=("$HOME/.claude/skills")

BACKUP_DIR="$HOME/.agents/skills-backup/$(date +%Y%m%d-%H%M%S)"
LINKED=0
UNCHANGED=0
SKIPPED=0
PRUNED=0

run() {
    if [[ "$DRY_RUN" == 1 ]]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

same_content() {
    diff -rq -x .DS_Store -x __pycache__ -x .venv "$1" "$2" > /dev/null 2>&1
}

link_skill() {
    local SRC="$1" DEST="$2" NAME
    NAME="$(basename "$SRC")"
    if [[ -L "$DEST" ]]; then
        if [[ "$(readlink "$DEST")" == "$SRC" ]]; then
            UNCHANGED=$((UNCHANGED + 1))
            return
        fi
        echo "relink  $NAME  ($(readlink "$DEST") -> repo)"
        run ln -sfn "$SRC" "$DEST"
    elif [[ -e "$DEST" ]]; then
        if same_content "$SRC" "$DEST"; then
            echo "replace $NAME  (identical copy -> link)"
            run rm -rf "$DEST"
        elif [[ "$FORCE" == 1 ]]; then
            echo "backup  $NAME  (differs; moved to ${BACKUP_DIR/#$HOME/~}/$NAME)"
            run mkdir -p "$BACKUP_DIR"
            run mv "$DEST" "$BACKUP_DIR/$NAME"
        else
            echo "SKIP    $NAME  (local copy differs: diff -ru \"$SRC\" \"$DEST\"; --force to back up and link)"
            SKIPPED=$((SKIPPED + 1))
            return
        fi
        run ln -s "$SRC" "$DEST"
    else
        echo "link    $NAME"
        run ln -s "$SRC" "$DEST"
    fi
    LINKED=$((LINKED + 1))
}

for TARGET in "${TARGETS[@]}"; do
    echo "==> ${TARGET/#$HOME/~}"
    run mkdir -p "$TARGET"

    for SKILL_MD in "$REPO_DIR"/*/SKILL.md; do
        SRC="$(dirname "$SKILL_MD")"
        link_skill "$SRC" "$TARGET/$(basename "$SRC")"
    done

    # Drop links into this repo whose skill no longer exists.
    for DEST in "$TARGET"/*; do
        if [[ -L "$DEST" && ! -e "$DEST" && "$(readlink "$DEST")" == "$REPO_DIR"/* ]]; then
            echo "prune   $(basename "$DEST")  (removed from repo)"
            run rm "$DEST"
            PRUNED=$((PRUNED + 1))
        fi
    done
done

echo "Done: $LINKED linked, $UNCHANGED already linked, $SKIPPED skipped, $PRUNED pruned."
[[ "$SKIPPED" == 0 ]]
