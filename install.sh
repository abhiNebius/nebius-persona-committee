#!/bin/zsh
# Installs every skill in skills/ (persona-committee, nebius-marketing-writer) into Claude Code and/or Codex by symlinking.
#   ./install.sh            install for every host found (Claude Code, Codex)
#   ./install.sh --claude   Claude Code only
#   ./install.sh --codex    Codex only
#   ./install.sh --remove   remove the symlinks (config is kept)
set -eu
REPO="${0:A:h}"
SKILLS=("$REPO"/skills/*(/))
CFG_DIR="$HOME/.config/persona-committee"
MODE="${1:-all}"

link() {
  mkdir -p "$1"
  for src in "${SKILLS[@]}"; do
    local dest="$1/${src:t}"
    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
      echo "  skip: $dest already exists as a real folder (kept as is)"; continue
    fi
    ln -sfn "$src" "$dest" && echo "  linked: $dest"
  done
}

unlink_host() {
  for src in "${SKILLS[@]}"; do
    local dest="$1/${src:t}"
    [ -L "$dest" ] && rm "$dest" && echo "  removed: $dest"
  done
  return 0
}

if [ "$MODE" = "--remove" ]; then
  unlink_host "$HOME/.claude/skills"; unlink_host "$HOME/.codex/skills"; exit 0
fi

echo "Installing ${#SKILLS[@]} skills from $REPO/skills"
{ [ "$MODE" = "all" ] || [ "$MODE" = "--claude" ]; } && link "$HOME/.claude/skills"
{ [ "$MODE" = "all" ] || [ "$MODE" = "--codex" ]; } && [ -d "$HOME/.codex" ] && link "$HOME/.codex/skills"

mkdir -p "$CFG_DIR"
if [ ! -f "$CFG_DIR/config.json" ]; then
  echo '{}' > "$CFG_DIR/config.json"
  echo "  created: $CFG_DIR/config.json (overrides only; defaults live in config/config.example.json)"
fi

echo "Checks:"
[ -n "${TAVILY_API_KEY:-}" ] && echo "  ok: TAVILY_API_KEY is set" || echo "  missing: TAVILY_API_KEY (runs will skip the live market check)"
command -v claude >/dev/null && echo "  ok: claude found" || echo "  note: claude not on PATH"
{ command -v codex >/dev/null || [ -x /Applications/ChatGPT.app/Contents/Resources/codex ]; } && echo "  ok: codex found" || echo "  note: codex not found"
python3 -c "import sys; assert sys.version_info >= (3, 9)" && echo "  ok: python3 >= 3.9 (standard library only, nothing to pip install)"
