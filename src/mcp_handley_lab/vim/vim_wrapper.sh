#!/bin/bash
# Wrapper script to run vim and signal completion

FILE="$1"
SIGNAL_FILE="$2"
shift 2

# Run vim with any additional arguments
vim "$@" "$FILE"

# Signal that vim has finished
echo "done" > "$SIGNAL_FILE"