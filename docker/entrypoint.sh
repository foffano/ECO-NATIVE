#!/bin/sh
set -eu
umask 077
if [ ! -w "${ECO_NATIVE_DATA_DIR:-/data}" ]; then
    echo "O diretório de dados precisa ser gravável pelo UID $(id -u)." >&2
    exit 1
fi
exec xvfb-run -a -s "-screen 0 1280x720x24 -nolisten tcp" "$@"
