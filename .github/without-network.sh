#!/bin/sh
# Run a command with no network access (Linux, needs sudo): in a new network
# namespace whose only interface is loopback. The command runs as root with
# the caller's environment.
#
#   sh .github/without-network.sh Rscript -e 'download.file(...)'   # fails
set -eu
exec sudo -E env "PATH=$PATH" unshare --net -- \
    sh -c 'ip link set lo up && exec "$@"' sh "$@"
