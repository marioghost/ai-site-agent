#!/usr/bin/env bash
# Canonical operator CLI for manage_deploy.sh — single public entry point.
set -euo pipefail

md_cli_usage() {
  cat <<'EOF'
AI Site Agent — operator CLI
Canonical entry: bash deploy/manage_deploy.sh <command>

Release workflow (main-only policy):
  release status              Git state + deploy readiness
  release prepare [--branch]  Review branch vs main before merge
  release merge [--branch]    Merge into main (interactive confirm)
  release push                Push main to origin (interactive confirm)
  release check               Full make release-check gate

Deploy (origin/main, clean worktree only):
  deploy full                 backup→build→deploy→verify→restart→smoke
  deploy backend              Backend path (mandatory backup)
  deploy frontend             Frontend path (mandatory backup)

Verification:
  status                      Concise repo/deploy/runtime identity report
  verify-release              End-to-end identity + health report
  smoke                       HTTP smoke (flags-off paths)
  build-info                  GET /api/build summary

Operations:
  doctor                      Pre-flight + git + DB connectivity
  health                      Health probes only
  backup db                   PostgreSQL pg_dump backup
  migrate                     Alembic upgrade head
  restart [all|backend|...]   Restart systemd modules
  logs [--module backend]     Service logs
  test unit                   Backend unit test subset

Interactive:
  (no args)                   Numbered menu

Legacy flags (deprecated):
  --mode full|backend|...     → use: deploy full|backend|...
  --action status|...         → use top-level commands above

Policy: deploy never uses dirty/feature checkouts; never deploys non-main;
backup is mandatory on release deploy (--no-backup-db refused);
all future deploy/release-engineering features live under manage_deploy.sh
(no new standalone deploy scripts except bootstrap/recovery).
Emergency bypass: EMERGENCY_DEPLOY_I_UNDERSTAND=YES + reason + confirm
  (never for routine Release work).
EOF
}

md_cli_repo() {
  local deploy_dir
  deploy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$deploy_dir/.." && pwd
}

md_invoke_legacy() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  MD_SKIP_CLI=1 exec bash "$script_dir/manage_deploy.sh" "$@"
}

md_cli_doctor() {
  local repo
  repo="$(md_cli_repo)"
  echo "=== Doctor ==="
  echo "Host: $(hostname) User: $(whoami)"
  # shellcheck source=deploy/lib/git_ops.sh
  source "$(dirname "${BASH_SOURCE[0]}")/git_ops.sh"
  md_git_print_status "$repo"
  md_invoke_legacy --action check-postgres || true
}

md_cli_release() {
  local sub="${1:-status}"
  shift || true
  local repo branch
  repo="$(md_cli_repo)"
  # shellcheck source=deploy/lib/git_ops.sh
  source "$(dirname "${BASH_SOURCE[0]}")/git_ops.sh"
  case "$sub" in
    status)
      md_git_print_status "$repo"
      echo ""
      if md_git_assert_deploy_ready "$repo" 2>/dev/null; then
        echo "Deploy readiness: OK (main clean, synced with origin/main)"
      else
        echo "Deploy readiness: NOT READY (see errors above)"
        return 1
      fi
      ;;
    prepare)
      branch="${MD_BRANCH:-}"
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --branch) branch="$2"; shift 2 ;;
          *) shift ;;
        esac
      done
      branch="${branch:-$(md_git_current_branch "$repo")}"
      md_git_prepare_branch_review "$repo" "$branch"
      ;;
    merge)
      branch=""
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --branch) branch="$2"; shift 2 ;;
          *) shift ;;
        esac
      done
      branch="${branch:-$(md_git_current_branch "$repo")}"
      md_git_merge_branch_to_main "$repo" "$branch"
      ;;
    push)
      md_git_push_main "$repo"
      ;;
    check)
      bash "$repo/scripts/release/release-check.sh"
      ;;
    *)
      echo "Unknown release subcommand: $sub" >&2
      return 1
      ;;
  esac
}

md_cli_deploy() {
  local sub="${1:-full}"
  shift || true
  # shellcheck source=deploy/lib/deploy_source.sh
  source "$(dirname "${BASH_SOURCE[0]}")/deploy_source.sh"
  case "$sub" in
    full) md_deploy_from_main full "$@" ;;
    backend) md_deploy_from_main backend "$@" ;;
    frontend) md_deploy_from_main frontend "$@" ;;
    *)
      echo "Unknown deploy subcommand: $sub (use full|backend|frontend)" >&2
      return 1
      ;;
  esac
}

md_cli_main() {
  local group sub
  if [[ $# -eq 0 ]]; then
    md_cli_usage
    return 0
  fi

  group="$1"
  shift

  case "$group" in
    help|-h|--help)
      md_cli_usage
      ;;
    release)
      sub="${1:-status}"
      shift || true
      md_cli_release "$sub" "$@"
      ;;
    deploy)
      sub="${1:-full}"
      shift || true
      md_cli_deploy "$sub" "$@"
      ;;
    verify-release|verify)
      bash "$(md_cli_repo)/scripts/release/verify-release.sh" "$@"
      ;;
    status)
      bash "$(md_cli_repo)/scripts/release/status-release.sh" "$@"
      ;;
    doctor)
      md_cli_doctor
      ;;
    health)
      md_invoke_legacy --action status
      ;;
    backup)
      [[ "${1:-db}" == "db" ]] || { echo "Use: backup db" >&2; return 1; }
      md_invoke_legacy --action backup-postgres --yes
      ;;
    migrate)
      md_invoke_legacy --action run-migrations
      ;;
    smoke)
      bash "$(md_cli_repo)/scripts/release/smoke-staging.sh"
      ;;
    restart)
      sub="${1:-all}"
      case "$sub" in
        all) md_invoke_legacy --action restart-all ;;
        backend) md_invoke_legacy --action restart --module backend ;;
        nginx) md_invoke_legacy --action restart --module nginx ;;
        *) md_invoke_legacy --action restart --module "$sub" ;;
      esac
      ;;
    logs)
      local mod=""
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --module) mod="$2"; shift 2 ;;
          *) shift ;;
        esac
      done
      md_invoke_legacy --action logs ${mod:+--module "$mod"}
      ;;
    build-info)
      curl -sf "http://127.0.0.1:8000/api/build" | python3 -m json.tool
      ;;
    test)
      sub="${1:-unit}"
      case "$sub" in
        unit) bash "$(md_cli_repo)/scripts/release/test-backend-unit.sh" ;;
        *) echo "Use: test unit" >&2; return 1 ;;
      esac
      ;;
    *)
      echo "Unknown command: $group" >&2
      md_cli_usage >&2
      return 1
      ;;
  esac
}
