#!/usr/bin/env bash
# Environment for prompt-pack task work in this repository.
#
#   source scripts/task_env.sh
#
# A prompt-pack worktree is a fresh git checkout, so it carries none of the
# gitignored runtime data: no decoded pixels, no thumbnails, no model binary,
# no database. This script points the application at the ONE verified artifact
# source on this machine and hands every task a THROWAWAY writable database.
#
# The canonical store is never opened for writing. OSTEOPATCH_DB is redirected
# to a per-task copy, so a task that inserts review events cannot mutate the
# evidence the next task depends on.
#
# Override the artifact root if your checkout lives elsewhere:
#   OSTEOPATCH_ARTIFACTS_ROOT=/path/to/runtime-artifacts source scripts/task_env.sh

# shellcheck disable=SC2155

# --- 1. Locate the repository root (this script lives in <root>/scripts) -----
TASK_ENV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TASK_ENV_ROOT

# --- 2. Find the verified read-only artifact source -------------------------
# Prefer an explicit override, then this worktree's own runtime-artifacts,
# then a sibling primary checkout that has them.
if [ -z "${OSTEOPATCH_ARTIFACTS_ROOT:-}" ]; then
  for candidate in \
      "${TASK_ENV_ROOT}/runtime-artifacts" \
      "$(cd "${TASK_ENV_ROOT}/../.." 2>/dev/null && pwd)/OsteoPatch_Kiro_Handoff/runtime-artifacts"
  do
    if [ -d "${candidate}/db" ]; then
      OSTEOPATCH_ARTIFACTS_ROOT="$(cd "${candidate}" && pwd)"
      break
    fi
  done
fi

if [ -z "${OSTEOPATCH_ARTIFACTS_ROOT:-}" ] || [ ! -d "${OSTEOPATCH_ARTIFACTS_ROOT}" ]; then
  echo "task_env.sh: could not locate a runtime-artifacts root." >&2
  echo "  Set OSTEOPATCH_ARTIFACTS_ROOT to the directory holding db/, images/," >&2
  echo "  thumbnails/ and models/. Aborting so no task runs without real data." >&2
  return 1 2>/dev/null || exit 1
fi

export OSTEOPATCH_ARTIFACTS_ROOT
# Read-only assets: pixels, thumbnails, model binaries, recovered head.
export OSTEOPATCH_RUNTIME_ARTIFACTS="${OSTEOPATCH_ARTIFACTS_ROOT}"

# --- 3. Throwaway writable database -----------------------------------------
# Seeded once from the canonical store, then owned entirely by this worktree.
TASK_THROW_DIR="${TASK_ENV_ROOT}/scratch/throwaway-db"
TASK_THROW_DB="${TASK_THROW_DIR}/throwaway.sqlite3"
mkdir -p "${TASK_THROW_DIR}"
if [ ! -f "${TASK_THROW_DB}" ]; then
  cp "${OSTEOPATCH_ARTIFACTS_ROOT}/db/osteopatch_g6.sqlite3" "${TASK_THROW_DB}"
fi
export OSTEOPATCH_DB="${TASK_THROW_DB}"

# Rebuildable caches stay inside the worktree, never in the shared root.
export OSTEOPATCH_SCRATCH="${TASK_ENV_ROOT}/scratch/task"
export OSTEOPATCH_ATTRIB_CACHE="${TASK_ENV_ROOT}/scratch/task/attribution-cache"
mkdir -p "${OSTEOPATCH_ATTRIB_CACHE}"

# --- 4. Report what was resolved -------------------------------------------
CANONICAL_DB="${OSTEOPATCH_ARTIFACTS_ROOT}/db/osteopatch_g6.sqlite3"
echo "task_env.sh:"
echo "  repo root        : ${TASK_ENV_ROOT}"
echo "  artifacts (RO)   : ${OSTEOPATCH_ARTIFACTS_ROOT}"
echo "  canonical store  : ${CANONICAL_DB}"
echo "  writable store   : ${TASK_THROW_DB}  (throwaway; never the canonical file)"
echo "  scratch          : ${OSTEOPATCH_SCRATCH}"
