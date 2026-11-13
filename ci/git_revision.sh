#!/usr/bin/env bash
# Trust only the explicitly owned checkout for this single metadata read.
# Container mounts can retain the host runner's uid. Never set safe.directory=*.
set -euo pipefail
root=$(cd "${1:?repository path required}" && pwd -P)
exec git -c "safe.directory=$root" -C "$root" rev-parse HEAD
