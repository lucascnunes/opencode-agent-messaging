#!/bin/sh
# Install the opencode-agent-messaging skill into your global OpenCode skills directory.
set -e

SKILL_ID="opencode-agent-messaging"
SRC="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/$SKILL_ID"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/$SKILL_ID"

if ! command -v opencode >/dev/null 2>&1; then
    echo "error: 'opencode' not found on PATH" >&2
    exit 1
fi

if [ ! -d "$SRC" ]; then
    echo "error: skill not found at $SRC" >&2
    exit 1
fi

if [ -e "$DEST" ]; then
    echo "note: replacing existing install at $DEST"
fi

mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"

echo "installed -> $DEST"
echo
echo "Restart OpenCode (or open a new session) so it discovers the skill."
echo "Sanity check:  opencode service status"