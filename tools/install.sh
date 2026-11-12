#!/usr/bin/env bash
# Install skills from this repo into an agent's skill folder, optionally adding private
# overlay files kept somewhere else.
#
# Usage: tools/install.sh --dest DIR [--overlays DIR] [--backup-dir DIR] [--apply] [skill...]
#   --dest DIR        skill folder, e.g. ~/.config/opencode/skill or ~/.claude/skills
#   --overlays DIR    folder with one subfolder per skill. Every file in it is copied on top
#                     (typically local.md). Two names are special:
#                       description.txt  appended to the description in SKILL.md's frontmatter
#                       preamble.md      inserted right after SKILL.md's frontmatter
#   --backup-dir DIR  where replaced skill folders go (default ~/.local/state/skill-backups)
#   --keep FILE       carry FILE over from the installed copy when the new one has none
#                     (repeatable; local.md is always kept)
#   --apply           actually install; without it, only show what would change
#   skill...          which skills (default: all under skills/)
# Only files tracked by git are installed.
set -eu

abspath() { # make a path absolute against the caller's current folder
  case "$1" in /*) printf '%s' "$1" ;; *) printf '%s/%s' "$PWD" "$1" ;; esac
}

DEST=""; OVER=""; BACKUP="$HOME/.local/state/skill-backups"; APPLY=0; NAMES=(); KEEP=(local.md)
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST=$(abspath "$2"); shift ;;
    --overlays) OVER=$(abspath "$2"); shift ;;
    --backup-dir) BACKUP=$(abspath "$2"); shift ;;
    --keep) [ $# -ge 2 ] || { echo "--keep needs a file name" >&2; exit 2; }; KEEP+=("$2"); shift ;;
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) NAMES+=("$1") ;;
  esac
  shift
done
[ -n "$DEST" ] || { echo "--dest is required" >&2; exit 2; }
for k in "${KEEP[@]}"; do
  case "$k" in ''|*/*|..|.) echo "--keep takes a file name, not a path: '$k'" >&2; exit 2 ;; esac
done
[ -z "$OVER" ] || [ -d "$OVER" ] || { echo "overlay folder not found: $OVER" >&2; exit 2; }
cd "$(dirname "$0")/.."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "run from a git checkout of this repo" >&2; exit 2; }
if [ ${#NAMES[@]} -eq 0 ]; then for d in skills/*/; do NAMES+=("$(basename "$d")"); done; fi

STAMP=$(date +%Y%m%d-%H%M%S)
for n in "${NAMES[@]}"; do
  [ -f "skills/$n/SKILL.md" ] || { echo "no such skill: $n" >&2; exit 2; }
  stage=$(mktemp -d); chmod 755 "$stage"
  git ls-files -z "skills/$n" | while IFS= read -r -d '' f; do
    rel=${f#skills/$n/}; mkdir -p "$stage/$(dirname "$rel")"; cp -p "$f" "$stage/$rel"
  done
  rm -f "$stage/local.md"
  note=""
  if [ -n "$OVER" ]; then
    if [ -d "$OVER/$n" ]; then
      (cd "$OVER/$n" && find . -type f ! -name description.txt ! -name preamble.md ! -name .DS_Store) |
        while IFS= read -r f; do mkdir -p "$stage/$(dirname "$f")"; cp -p "$OVER/$n/$f" "$stage/$f"; done
      if [ -f "$OVER/$n/description.txt" ] || [ -f "$OVER/$n/preamble.md" ]; then
        python3 - "$stage/SKILL.md" "$OVER/$n/description.txt" "$OVER/$n/preamble.md" <<'PY'
import json, os, sys
skill, desc, pre = sys.argv[1:4]
text = open(skill).read()
if not text.startswith("---\n"):
    sys.exit("SKILL.md has no frontmatter")
end = text.index("\n---\n", 4)
head, body = text[4:end], text[end + 5:]
if os.path.exists(desc):
    extra = " ".join(open(desc).read().split())
    lines = head.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value[:1] in "\"'":
                sys.exit("quoted descriptions are not supported; leave the public one unquoted")
            # JSON strings are valid YAML, so colons in the combined text are safe
            lines[i] = "description: " + json.dumps(value + " " + extra, ensure_ascii=False)
            break
    else:
        sys.exit("SKILL.md frontmatter has no description line")
    head = "\n".join(lines)
if os.path.exists(pre):
    body = "\n" + open(pre).read().strip() + "\n" + body
open(skill, "w").write("---\n" + head + "\n---\n" + body)
PY
      fi
      note="with overlay"
    else
      note="WARNING: no overlay folder for $n in $OVER"
    fi
  fi
  for k in "${KEEP[@]}"; do
    if [ ! -e "$stage/$k" ] && [ -f "$DEST/$n/$k" ]; then
      cp -p "$DEST/$n/$k" "$stage/$k"; note="${note:+$note; }kept existing $k"
    fi
  done
  if [ -d "$DEST/$n" ]; then
    changes=$(diff -rq "$DEST/$n" "$stage" 2>/dev/null | sed "s|$stage|<new>|g; s|$DEST/$n|<installed>|g" || true)
  else
    changes="new skill"
  fi
  [ -z "$note" ] || echo "$n: $note"
  if [ -z "$changes" ]; then echo "$n: up to date"; rm -rf "$stage"; continue; fi
  echo "$n:"; echo "$changes" | sed 's|^|  |'
  if [ $APPLY = 1 ]; then
    if [ -d "$DEST/$n" ]; then
      mkdir -p "$BACKUP/$STAMP"; mv "$DEST/$n" "$BACKUP/$STAMP/$n"; echo "  old copy moved to $BACKUP/$STAMP/$n"
    fi
    mkdir -p "$DEST"; mv "$stage" "$DEST/$n"
    echo "  installed"
  else
    rm -rf "$stage"
  fi
done
[ $APPLY = 1 ] || echo "(dry run; add --apply to install)"
