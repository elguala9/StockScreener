#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
die() { echo -e "${RED}❌ $*${NC}" >&2; exit 1; }
info() { echo -e "${CYAN}→ $*${NC}"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; }

command -v gh  >/dev/null 2>&1 || die "gh (GitHub CLI) non installato"
command -v git >/dev/null 2>&1 || die "git non installato"

gh auth status 2>/dev/null || die "gh non autenticato — esegui: gh auth login"

cd "$(dirname "$0")"
git rev-parse --git-dir >/dev/null 2>&1 || die "non sei in un repository git"

REMOTE=$(git remote get-url GitHub 2>/dev/null) || die "remote 'GitHub' non configurato"
info "repo: $(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "$REMOTE")"

if ! git diff --quiet || ! git diff --cached --quiet; then
    info "commit delle modifiche in corso..."
    git add -A
    git commit -m "build $(date +%Y-%m-%d)"
fi

if [ "$(git rev-parse HEAD)" != "$(git rev-parse @{upstream} 2>/dev/null || true)" ]; then
    info "push in corso..."
    git push GitHub HEAD
fi

info "avvio workflow..."
gh workflow run build.yml

RUN_URL=$(gh run list --workflow=build.yml --limit=1 --json url -q '.[0].url 2>/dev/null' 2>/dev/null || true)
ok "workflow avviato!${RUN_URL:+ Monitora: $RUN_URL}"
