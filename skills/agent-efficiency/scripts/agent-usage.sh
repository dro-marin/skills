#!/usr/bin/env bash
# Model usage by agent from OpenCode's local session database (read-only).
#
# Usage: agent-usage.sh [days=7] [--db PATH] [--ssh HOST]... [--remote-db PATH] [--save]
#   --db PATH         local database (default: $OPENCODE_DB or ~/.local/share/opencode/opencode.db)
#   --ssh HOST        also query HOST over SSH (repeatable; HOST needs sqlite3). Capped at 10 minutes.
#   --remote-db PATH  database path on the SSH hosts (default: ~/.local/share/opencode/opencode.db)
#   --save            write a snapshot to $AGENT_USAGE_DIR (default ~/.local/state/agent-efficiency)
#
# Output: a "## <machine>" header per machine, then rows: agent model variant calls api_usd cache_read_M.
# Exits 1 if no machine returned data.
set -u

DAYS=7
DB="${OPENCODE_DB:-$HOME/.local/share/opencode/opencode.db}"
REMOTE_DB='~/.local/share/opencode/opencode.db'
SAVE=0
HOSTS=()
OUTDIR="${AGENT_USAGE_DIR:-$HOME/.local/state/agent-efficiency}"

while [ $# -gt 0 ]; do
  case "$1" in
    --db) DB="$2"; shift ;;
    --ssh) HOSTS+=("$2"); shift ;;
    --remote-db) REMOTE_DB="$2"; shift ;;
    --save) SAVE=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    [0-9]*) DAYS="$1" ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$DAYS" in ''|*[!0-9]*) echo "days must be a whole number" >&2; exit 2 ;; esac
command -v sqlite3 >/dev/null || { echo "sqlite3 is required" >&2; exit 2; }

SQL="with m as (
  select json_extract(data,'\$.agent') agent,
         json_extract(data,'\$.model.providerID')||'/'||json_extract(data,'\$.model.id') model,
         coalesce(json_extract(data,'\$.model.variant'),'default') variant,
         coalesce(json_extract(data,'\$.cost'),0) cost,
         coalesce(json_extract(data,'\$.tokens.cache.read'),0) cread
  from session_message
  where type='assistant' and time_created > (strftime('%s','now')-$DAYS*86400)*1000)
select agent, model, variant, count(*), round(sum(cost),2), round(sum(cread)/1e6,1)
from m group by 1,2,3 order by 5 desc;"

run_local() {
  if [ ! -f "$DB" ]; then echo "no database at $DB (set --db or OPENCODE_DB)" >&2; return 1; fi
  sqlite3 -readonly -separator $'\t' "$DB" "$SQL"
}

run_remote() { # host
  local db
  case "$REMOTE_DB" in '~/'*) db="\$HOME/$(printf '%q' "${REMOTE_DB#'~/'}")" ;; *) db=$(printf '%q' "$REMOTE_DB") ;; esac
  printf '%s' "$SQL" | ssh -o BatchMode=yes -o ControlMaster=no -o ConnectTimeout=10 "$1" \
    "if command -v timeout >/dev/null; then timeout 600 nice -n 10 sqlite3 -readonly -separator '	' $db; else nice -n 10 sqlite3 -readonly -separator '	' $db; fi" 2>/dev/null
}

GOT=0
emit() { # machine-label data
  local name="$1" data="$2" safe prev
  if [ -z "$data" ]; then echo "## $name: no data (unreachable, empty, or timed out)"; return; fi
  GOT=1
  echo "## $name (last $DAYS days)  columns: agent model variant calls api_usd cache_read_M"
  echo "$data"
  safe=$(printf '%s' "$name" | tr -c 'A-Za-z0-9._-' '_')
  if [ "$SAVE" = 1 ]; then
    mkdir -p "$OUTDIR"
    prev=$(ls -1 "$OUTDIR"/*-"$safe"-"${DAYS}"d.tsv 2>/dev/null | grep -v "/$(date +%F)-" | tail -1)
    echo "$data" > "$OUTDIR/$(date +%F)-$safe-${DAYS}d.tsv"
    echo "## saved $OUTDIR/$(date +%F)-$safe-${DAYS}d.tsv"
    [ -n "$prev" ] && echo "## previous snapshot: $prev"
  fi
}

emit "local" "$(run_local)"
for h in ${HOSTS[@]+"${HOSTS[@]}"}; do emit "$h" "$(run_remote "$h")"; done
[ "$GOT" = 1 ] || exit 1
exit 0
