#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
die() { echo -e "${RED}❌ $*${NC}" >&2; exit 1; }
info() { echo -e "${CYAN}→ $*${NC}"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; }

command -v gh      >/dev/null 2>&1 || die "gh (GitHub CLI) non installato"
command -v git     >/dev/null 2>&1 || die "git non installato"
command -v python3 >/dev/null 2>&1 || die "python3 non installato"

gh auth status 2>/dev/null || die "gh non autenticato — esegui: gh auth login"

cd "$(dirname "$0")"
git rev-parse --git-dir >/dev/null 2>&1 || die "non sei in un repository git"

REMOTE=$(git remote get-url GitHub 2>/dev/null) || die "remote 'GitHub' non configurato"
info "repo: $(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "$REMOTE")"

# read version from pyproject.toml
VERSION=$(python3 -c "
import re
with open('pyproject.toml') as f:
    for line in f:
        m = re.match(r'^version\s*=\s*\"(.+?)\"', line)
        if m:
            print(m.group(1))
            break
")
[ -n "$VERSION" ] || die "versione non trovata in pyproject.toml"

TAG="v$VERSION"

if gh release view "$TAG" --json tagName 2>/dev/null | grep -q .; then
    die "la release $TAG esiste già su GitHub — aggiorna la versione in pyproject.toml"
fi

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
    info "rimozione tag locale $TAG..."
    git tag -d "$TAG"
fi

if git ls-remote --tags "$REMOTE" "refs/tags/$TAG" | grep -q .; then
    info "rimozione tag remoto $TAG..."
    git push --delete GitHub "$TAG"
fi

info "versione: $VERSION"

if ! git diff --quiet || ! git diff --cached --quiet; then
    info "commit delle modifiche in corso..."
    git add -A
    git commit -m "release $TAG"
fi

info "creazione tag $TAG..."
git tag "$TAG"

if [ "$(git rev-parse HEAD)" != "$(git rev-parse @{upstream} 2>/dev/null || true)" ]; then
    info "push in corso..."
    git push GitHub HEAD
fi

info "push tag in corso..."
git push GitHub "$TAG"

# workflow avviato automaticamente dal push del tag

ok "release $TAG creata e pubblicata!"
