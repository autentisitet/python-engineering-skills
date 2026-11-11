#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf 'Usage: bash scripts/links/install.sh /path/to/project [skill ...]\nRequires Bash 4+ and GNU find/readlink.\n'
  exit 0
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if (( $# == 0 )); then
  echo "usage: ./scripts/links/install.sh /path/to/python-project [skill ...]" >&2
  exit 2
fi
target_project="$1"
shift
target_project="$(cd "$target_project" && pwd)"
dest="$target_project/.agents/skills"

if [[ "$target_project" == "$repo" ]]; then
  echo "error: choose a target Python project, not the skill source repository" >&2
  echo "usage: ./scripts/links/install.sh /path/to/python-project [skill ...]" >&2
  exit 2
fi

if [[ -L "$target_project/.agents" || -L "$dest" ]]; then
  echo "error: refusing to install through a symbolic-link destination" >&2
  exit 1
fi

mkdir -p "$dest"

if (( $# == 0 )); then
  mapfile -t selected < <(find "$repo/skills" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
else
  selected=("$@")
fi

for name in "${selected[@]}"; do
  if [[ ! "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "error: invalid skill name: $name" >&2
    exit 2
  fi
  source_dir="$repo/skills/$name"
  target="$dest/$name"

  if [[ ! -f "$source_dir/SKILL.md" ]]; then
    echo "error: unknown skill: $name" >&2
    exit 2
  fi

  if [[ -L "$target" ]]; then
    current="$(readlink -f "$target" 2>/dev/null || true)"
    if [[ ! -e "$target" ]]; then
      echo "error: refusing to replace broken symbolic link: $target" >&2
      echo "remove it explicitly or run uninstall.sh --remove-broken" >&2
      exit 1
    fi
    if [[ "$current" == "$source_dir" ]]; then
      echo "keep  $name"
      continue
    fi
    echo "error: $target links to another location: $current" >&2
    exit 1
  fi

  if [[ -e "$target" ]]; then
    echo "error: refusing to replace existing path: $target" >&2
    exit 1
  fi

  ln -s "$source_dir" "$target"
  echo "link  $name -> $target"
done

echo "Project skills are available in $dest"
