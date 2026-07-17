#!/bin/sh
# Install a pre-commit hook that auto-refreshes the self-knowledge doc and stages
# it, so it never drifts from the code. Idempotent; refuses to clobber a foreign
# hook without --force.
#
#   sh scripts/install-self-knowledge-hook.sh          # install
#   sh scripts/install-self-knowledge-hook.sh --force  # overwrite an existing hook

set -e
MARKER="trillion-self-knowledge-hook"
HOOK_DIR="$(git rev-parse --git-path hooks)"
HOOK="$HOOK_DIR/pre-commit"
FORCE=0
[ "$1" = "--force" ] && FORCE=1

if [ -f "$HOOK" ]; then
  if grep -q "$MARKER" "$HOOK" 2>/dev/null; then
    echo "self-knowledge pre-commit hook already installed."
    exit 0
  fi
  if [ "$FORCE" != "1" ]; then
    echo "Refusing to overwrite an existing pre-commit hook (use --force)."
    exit 1
  fi
fi

mkdir -p "$HOOK_DIR"
cat > "$HOOK" <<'EOF'
#!/bin/sh
# trillion-self-knowledge-hook — keep context/self/trillion.md in sync with code.
# Local + fast, no network. Never blocks a commit on failure.
python -m trillion.self_knowledge --refresh >/dev/null 2>&1 || true
git add context/self/trillion.md >/dev/null 2>&1 || true
EOF
chmod +x "$HOOK"
echo "Installed self-knowledge pre-commit hook at $HOOK"
