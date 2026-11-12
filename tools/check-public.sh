#!/usr/bin/env bash
# Check that the repo is safe to publish. Looks at file contents, file names and the full git
# history (commit authors, messages and every past version of every file) for: local overlay
# files, personal paths, emails, private IP addresses, key-shaped strings and long ids.
#
# Usage: tools/check-public.sh [--deny-file FILE] [--no-history]
#   --deny-file FILE  extra extended regexes, one per line (company names, hosts, database names...).
#                     Prefix a line with "i:" to match it case-insensitively. Keep the file OUTSIDE
#                     this repo: it lists exactly what must not leak.
#   --no-history      only check the current files (default also checks git history)
# No-reply commit author addresses (noreply@..., ...@users.noreply.github.com) are allowed.
# Exit 0 = clean, 1 = findings, 2 = usage error.
set -u
cd "$(dirname "$0")/.." || exit 2

DENY=""; HISTORY=1
while [ $# -gt 0 ]; do
  case "$1" in
    --deny-file) DENY="$2"; shift ;;
    --no-history) HISTORY=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ -n "$DENY" ] && [ ! -f "$DENY" ]; then echo "deny file not found: $DENY" >&2; exit 2; fi

SELF=tools/check-public.sh
ALL=$(git ls-files --cached --others --exclude-standard)
[ -n "$ALL" ] || { echo "no files to check" >&2; exit 2; }
# The built-in patterns below would match this script itself; the deny list still checks it.
FILES=$(echo "$ALL" | grep -vx "$SELF")
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
if [ $HISTORY = 1 ] && git rev-parse -q --verify HEAD >/dev/null; then
  # No-reply author addresses are allowed: they are removed here, and the rest of each line is still checked.
  git log --all --format='commit %H%nauthor: %an <%ae> %ad%ncommitter: %cn <%ce> %cd%n%B' |
    sed -E 's/<[^>]*(noreply@|@users\.noreply\.github\.com)[^>]*>/<no-reply>/g' > "$TMP/meta"
  git log --all -p --format='commit %H' -- . ":(exclude)$SELF" > "$TMP/patches"
fi
FOUND=0

report() { # label matches
  if [ -n "$2" ]; then echo "== $1"; echo "$2" | head -20; FOUND=1; fi
}

check() { # label flags regex files...
  local label="$1" flags="$2" re="$3"; shift 3
  report "$label (files)" "$(printf '%s\0' "$@" | xargs -0 grep -nH$flags -e "$re" 2>/dev/null)"
  report "$label (file names)" "$(printf '%s\n' "$@" | grep -$flags -e "$re")"
  if [ -f "$TMP/meta" ]; then
    report "$label (commit authors and messages)" "$(grep -$flags -e "$re" "$TMP/meta")"
    report "$label (git history)" "$(grep -e "^[+-]" "$TMP/patches" | grep -$flags -e "$re")"
  fi
}

report "local overlay files (must never be committed)" "$(echo "$ALL" | grep -E '(^|/)local\.md$')"

# shellcheck disable=SC2086
set -- $FILES
check "absolute home paths" IE '/Users/[A-Za-z0-9._-]+|/home/[a-z][a-z0-9_-]+/' "$@"
check "email addresses" IE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$@"
check "private or VPN IP addresses" IE '\b(10\.[0-9]{1,3}|192\.168|172\.(1[6-9]|2[0-9]|3[01])|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7]))\.[0-9]{1,3}\.[0-9]{1,3}\b' "$@"
check "key-shaped strings" IE '\b(sk-[A-Za-z0-9_-]{16,}|re_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9-]{10,}|tr_(dev|prod)_[A-Za-z0-9]{10,})' "$@"
check "long ids (account, project, database ids)" IE '\b[0-9a-f]{32}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\bproj_[a-z0-9]{16,}' "$@"
check "connection strings with passwords" IE '[a-z]+://[^/ :]+:[^@ ]+@' "$@"
check "session ids" IE '\bses_[A-Za-z0-9]{10,}' "$@"

if [ -n "$DENY" ]; then
  # shellcheck disable=SC2086
  set -- $ALL
  while IFS= read -r pat || [ -n "$pat" ]; do
    case "$pat" in ''|'#'*) continue ;; i:*) flags=IEi; pat="${pat#i:}" ;; *) flags=IE ;; esac
    check "deny list: $pat" "$flags" "$pat" "$@"
  done < "$DENY"
fi

if [ $FOUND = 0 ]; then
  scope="files"; [ -f "$TMP/meta" ] && scope="files and git history"
  echo "clean: $(echo "$ALL" | wc -l | tr -d ' ') $scope checked${DENY:+, deny list applied}"
fi
exit $FOUND
