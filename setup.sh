#!/bin/sh
# ubuntu-mini: run after installing Ubuntu 24.04 Server.
set -eu
setup_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$setup_root/setup/base/setup.py" "$@"
