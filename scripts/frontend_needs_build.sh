#!/usr/bin/env bash

frontend_dir="${1:-src/frontend}"
output="$frontend_dir/dist/index.html"

[[ ! -f "$output" ]] && exit 0

find "$frontend_dir/src" "$frontend_dir/index.html" "$frontend_dir/package.json" "$frontend_dir/vite.config.js" \
    -type f -newer "$output" -print -quit 2>/dev/null | grep -q . && exit 0

exit 1
