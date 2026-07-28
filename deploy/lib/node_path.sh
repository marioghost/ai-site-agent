#!/usr/bin/env bash
# Node/npm PATH resolution for sudo deploy builds (nvm not on default PATH).
set -euo pipefail

md_prepend_path_dir() {
  local dir="$1"
  [[ -n "$dir" && -d "$dir" ]] || return 0
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) PATH="$dir:$PATH" ;;
  esac
}

md_augment_path_for_node() {
  if [[ -n "${NPM_BIN:-}" ]]; then
    md_prepend_path_dir "$(dirname "$NPM_BIN")"
  fi
  if [[ -n "${NODE_BIN:-}" ]]; then
    md_prepend_path_dir "$(dirname "$NODE_BIN")"
  fi
  local owner home nvm_bin
  owner="${SUDO_USER:-${USER:-}}"
  if [[ -n "$owner" && "$owner" != "root" ]]; then
    home="$(getent passwd "$owner" 2>/dev/null | cut -d: -f6 || true)"
    if [[ -n "$home" && -d "$home/.nvm/versions/node" ]]; then
      nvm_bin="$(ls -1d "$home/.nvm/versions/node/"*/bin 2>/dev/null | sort -V | tail -1 || true)"
      md_prepend_path_dir "$nvm_bin"
    fi
  fi
  md_prepend_path_dir "/usr/local/bin"
  export PATH
}

md_npm_cmd() {
  if [[ -n "${NPM_BIN:-}" && -x "$NPM_BIN" ]]; then
    echo "$NPM_BIN"
  elif command -v npm &>/dev/null; then
    command -v npm
  else
    local owner home nvm_bin
    owner="${SUDO_USER:-${USER:-}}"
    if [[ -n "$owner" && "$owner" != "root" ]]; then
      home="$(getent passwd "$owner" 2>/dev/null | cut -d: -f6 || true)"
      if [[ -n "$home" && -d "$home/.nvm/versions/node" ]]; then
        nvm_bin="$(ls -1d "$home/.nvm/versions/node/"*/bin/npm 2>/dev/null | sort -V | tail -1 || true)"
        if [[ -x "$nvm_bin" ]]; then
          echo "$nvm_bin"
          return 0
        fi
      fi
    fi
    return 1
  fi
}
