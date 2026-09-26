#!/usr/bin/env bash
# Run the bundled Linux taxsimtest binary through Docker, e.g. to check
# taxsimtest-linux.exe from a Mac:
#
#   resources/taxsimtest/taxsim-docker-wrapper.sh < input.txt > output.csv
#
# The binary is the taxsimtest-linux.exe next to this script; set
# TAXSIM_LINUX_BINARY to run another build (e.g. a new download, before it
# replaces the bundled copy). It runs in the image defined by
# taxsimtest-linux.Dockerfile (ubuntu:24.04 plus the gfortran runtime), which
# is built on first use and tagged with a hash of the Dockerfile, so editing
# the Dockerfile triggers a rebuild.
#
# Docker bind-mounts the binary, so it must sit in a directory that the Docker
# VM shares with the host. colima shares only $HOME by default: a file outside
# it (such as under /private/tmp) shows up in the container as an empty
# directory. See README.md in this directory.
set -euo pipefail

abs_dir() { CDPATH='' cd -- "$1" && pwd; }

# Resolve this script's own directory, following symlinks (e.g. from ~/bin).
src="${BASH_SOURCE[0]}"
while [ -L "$src" ]; do
  link="$(readlink "$src")"
  case "$link" in
  /*) src="$link" ;;
  *) src="$(dirname -- "$src")/$link" ;;
  esac
done
here="$(abs_dir "$(dirname -- "$src")")"
binary="${TAXSIM_LINUX_BINARY:-$here/taxsimtest-linux.exe}"
dockerfile="$here/taxsimtest-linux.Dockerfile"
platform=linux/amd64 # the binary is x86-64 only; Apple silicon emulates it

if [ ! -f "$binary" ]; then
  echo "taxsim-docker-wrapper: binary not found: $binary" >&2
  exit 1
fi
# A bind mount needs an absolute host path.
binary="$(abs_dir "$(dirname -- "$binary")")/$(basename -- "$binary")"

if command -v sha256sum >/dev/null 2>&1; then
  tag="$(sha256sum <"$dockerfile" | cut -c1-12)"
else
  tag="$(shasum -a 256 <"$dockerfile" | cut -c1-12)"
fi
image="policyengine-taxsim-linux:$tag"

if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "taxsim-docker-wrapper: building $image (first run only)" >&2
  # Build from stdin: the image needs no files from this directory.
  docker build --platform "$platform" -t "$image" - <"$dockerfile" >&2
fi

# Run a copy of the binary: a bind mount keeps the host file's mode, and the
# host copy may not be executable (TaxsimRunner likewise chmods it first).
exec docker run --platform "$platform" --rm -i \
  -v "$binary:/taxsim:ro" \
  "$image" \
  sh -c '
    if [ ! -f /taxsim ]; then
      echo "taxsim-docker-wrapper: $1 mounted as an empty directory, so the Docker VM cannot see it." >&2
      echo "Keep it under a directory the VM shares with the host, such as \$HOME (colima shares only \$HOME by default)." >&2
      exit 126
    fi
    cp /taxsim /tmp/taxsim && chmod 755 /tmp/taxsim && exec /tmp/taxsim
  ' sh "$binary"
