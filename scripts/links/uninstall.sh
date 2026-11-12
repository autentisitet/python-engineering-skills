#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf 'Usage: bash scripts/links/uninstall.sh [--remove-broken] /path/to/project [skill ...]\nRequires Bash 4+ and GNU find/readlink.\n'
  exit 0
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
remove_broken=false
if [[ "${1:-}" == "--remove-broken" ]]; then
  remove_broken=true
  shift
fi
if (( $# == 0 )); then
  echo "usage: ./scripts/links/uninstall.sh [--remove-broken] /path/to/project [skill ...]" >&2
  exit 2
fi
target_project="$1"
shift
target_project="$(cd "$target_project" && pwd)"
dest="$target_project/.agents/skills"

if [[ -L "$target_project/.agents" || -L "$dest" ]]; then
  echo "error: refusing to remove through a symbolic-link destination" >&2
  exit 1
fi

if [[ ! -d "$dest" ]]; then
  echo "No project skill directory: $dest"
  exit 0
fi

if (( $# == 0 )); then
  mapfile -t selected < <(find "$repo/skills" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
else
  selected=("$@")
fi

# Reject an invalid request before removing any links.
for name in "${selected[@]}"; do
  if [[ ! "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "error: invalid skill name: $name" >&2
    exit 2
  fi
done

for name in "${selected[@]}"; do
  target="$dest/$name"
  source_dir="$repo/skills/$name"

  if [[ ! -L "$target" ]]; then
    if [[ -e "$target" ]]; then
      echo "skip  $name (not a symbolic link)"
    fi
    continue
  fi

  current="$(readlink -f "$target" 2>/dev/null || true)"
  if [[ ! -e "$target" ]]; then
    if [[ "$remove_broken" == true ]]; then
      rm "$target"
      echo "unlink $name (broken symbolic link)"
    else
      echo "skip  $name (broken symbolic link; rerun with --remove-broken to remove it)"
    fi
    continue
  fi
  if [[ "$current" != "$source_dir" ]]; then
    echo "skip  $name (link is not managed by this repository)"
    continue
  fi

  rm "$target"
  echo "unlink $name"
done

rmdir "$dest" 2>/dev/null || true
rmdir "$target_project/.agents" 2>/dev/null || true
