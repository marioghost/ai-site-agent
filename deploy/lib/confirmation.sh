#!/usr/bin/env bash
# Shared operator confirmation helpers.
set -euo pipefail

# Non-interactive: require MD_ASSUME_YES=1 or explicit --yes on subcommand.
md_confirm() {
  local question="$1"
  local default="${2:-n}"
  if [[ "${MD_ASSUME_YES:-0}" == "1" || "${ASSUME_YES:-0}" == "1" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "ERROR: confirmation required but not interactive: $question" >&2
    return 1
  fi
  local hint="y/N"
  [[ "$default" == "y" || "$default" == "Y" ]] && hint="Y/n"
  local reply
  read -r -p "$question [$hint] " reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy] ]]
}

md_confirm_destructive_db() {
  local db_name="$1"
  local action="${2:-destructive operation}"
  echo ""
  echo "WARNING: $action targets database: $db_name"
  echo "Environment: PROJECT_ROOT=${PROJECT_ROOT:-?} DATABASE_URL host=${PG_HOST:-?}"
  if [[ "${MD_ASSUME_YES:-0}" == "1" ]]; then
    echo "ERROR: destructive action refused without interactive confirmation" >&2
    return 1
  fi
  local typed
  read -r -p "Type database name to confirm ($db_name): " typed
  [[ "$typed" == "$db_name" ]]
}

md_confirm_typed() {
  local prompt="$1"
  local expected="$2"
  if [[ "${MD_ASSUME_YES:-0}" == "1" ]]; then
    echo "ERROR: typed confirmation required: $prompt" >&2
    return 1
  fi
  local typed
  read -r -p "$prompt " typed
  [[ "$typed" == "$expected" ]]
}
