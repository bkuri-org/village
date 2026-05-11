#!/usr/bin/env sh
# Check that beads config.yaml and metadata.json agree on the backend.
# Prevents silent data loss from git checkout reverting metadata.json.
#
# Expected backend mapping:
#   config.yaml  no-db: true  → metadata.json  backend: jsonl, database: jsonl
#   config.yaml  no-db: false → metadata.json  backend: dolt

set -e

BEADS_DIR="$(git rev-parse --show-toplevel 2>/dev/null)/.beads" || exit 0
[ -f "$BEADS_DIR/config.yaml" ] || exit 0
[ -f "$BEADS_DIR/metadata.json" ] || exit 0

# Extract no-db setting (default: false)
_no_db=$(grep -E '^\s*no-db\s*:' "$BEADS_DIR/config.yaml" 2>/dev/null | grep -oE '(true|false)' | tail -1)
_no_db="${_no_db:-false}"

# Extract backend from metadata.json
_backend=$(python3 -c "
import json, sys
try:
    with open('$BEADS_DIR/metadata.json') as f:
        m = json.load(f)
    print(m.get('backend', ''))
except Exception:
    print('')
" 2>/dev/null)

# Determine expected backend
if [ "$_no_db" = "true" ]; then
    _expected="jsonl"
else
    _expected="dolt"
fi

if [ "$_backend" != "$_expected" ]; then
    echo "" >&2
    echo "⚠  BEADS BACKEND MISMATCH DETECTED" >&2
    echo "  config.yaml  no-db: $_no_db  → expected backend: $_expected" >&2
    echo "  metadata.json backend: $_backend" >&2
    echo "" >&2
    echo "  This usually happens after 'git checkout' reverts metadata.json." >&2
    echo "  Fix:" >&2
    if [ "$_expected" = "jsonl" ]; then
        echo "    python3 -c \"import json; m=json.load(open('$BEADS_DIR/metadata.json')); m['backend']=m['database']='jsonl'; json.dump(m,open('$BEADS_DIR/metadata.json','w'),indent=4)\"" >&2
    else
        echo "    python3 -c \"import json; m=json.load(open('$BEADS_DIR/metadata.json')); m['backend']='dolt'; json.dump(m,open('$BEADS_DIR/metadata.json','w'),indent=4)\"" >&2
        echo "    bd bootstrap -y" >&2
    fi
    echo "" >&2
    # Don't block the checkout — just warn loudly
fi
