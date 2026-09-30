#!/usr/bin/env bash
# Locate the python 3 for conspire and print its path. Hooks and cron
# don't run in an interactive shell, so PATH may lack the python you
# use day to day; set CONSPIRE_PYTHON in a machine-local profile (or in
# the hook's environment) to name it explicitly. Order:
#   1. $CONSPIRE_PYTHON
#   2. python3 / python on PATH
# Invoke as: bash find_python.sh  (no exec bit required)
try() { [ -n "$1" ] && [ -x "$1" ] && { printf '%s\n' "$1"; exit 0; }; }
try "${CONSPIRE_PYTHON:-}"
command -v python3 && exit 0
command -v python && exit 0
exit 1
