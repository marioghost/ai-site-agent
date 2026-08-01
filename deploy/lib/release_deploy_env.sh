#!/usr/bin/env bash
# Preserve release-pipeline env across deploy.local.conf for One Command deploy.
# When MD_RELEASE_DEPLOY=1, an already-exported DEV_CHECKOUT (release worktree)
# and MD_DEPLOY_RELEASE (tip APP_RELEASE) must not be overwritten by local conf.
#
# Do not enable set -e/-u here — this file is sourced into manage_deploy.sh.

md_release_preserve_env_before_local_conf() {
  MD_RELEASE_SAVED_DEV_CHECKOUT=""
  MD_RELEASE_SAVED_RELEASE_VERSION=""
  if [[ "${MD_RELEASE_DEPLOY:-0}" != "1" ]]; then
    return 0
  fi
  if [[ -n "${DEV_CHECKOUT:-}" ]]; then
    MD_RELEASE_SAVED_DEV_CHECKOUT="$DEV_CHECKOUT"
  fi
  # Tip APP_RELEASE identity — never let stale RELEASE_VERSION from local conf win.
  if [[ -n "${MD_DEPLOY_RELEASE:-}" ]]; then
    MD_RELEASE_SAVED_RELEASE_VERSION="$MD_DEPLOY_RELEASE"
  fi
}

md_release_restore_env_after_local_conf() {
  if [[ -n "${MD_RELEASE_SAVED_DEV_CHECKOUT:-}" ]]; then
    DEV_CHECKOUT="$MD_RELEASE_SAVED_DEV_CHECKOUT"
  fi
  if [[ -n "${MD_RELEASE_SAVED_RELEASE_VERSION:-}" ]]; then
    RELEASE_VERSION="$MD_RELEASE_SAVED_RELEASE_VERSION"
  fi
}
