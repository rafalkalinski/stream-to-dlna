#!/bin/sh
# Print the app version: MAJOR.MINOR from the latest vMAJOR.MINOR git tag,
# PATCH = number of commits on the first-parent (main) line since that tag.
# With --no-ff merges every merged change bumps PATCH by exactly one:
#   tag v0.6 -> 0.6.0, next merge -> 0.6.1, ...
# Prints 0.0.0 when no tag / git history is available.
set -e
tag=$(git describe --tags --abbrev=0 --first-parent --match 'v[0-9]*' 2>/dev/null) || { echo "0.0.0"; exit 0; }
count=$(git rev-list --count --first-parent "${tag}..HEAD")
echo "${tag#v}.${count}"
