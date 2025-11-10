#!/bin/bash

set -euo pipefail

usage() {
  echo "Usage: $0 {up|down} role"
  echo "  up   - Bring the role up"
  echo "  down - Bring the role down"
}

declare verbosity
if [[ "$1" =~ ^-vv*$ ]]; then
  verbosity="$1"
  shift
fi

declare state=""
case "$1" in
"up")
  state=present
  ;;
"down")
  state=absent
  ;;
"*")
  usage
  exit 16
  ;;
esac

role="$2"
if [ -z "$role" ]; then
  usage
  exit 16
fi

# Ansible needs this to work with modern macos (for now)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
export ANSIBLE_PYTHON_INTERPRETER="$SCRIPT_DIR/../.venv/bin/python"

(
  ansible $verbosity -i inventory.ini \
    --module-path ./library \
    --module-name ansible.builtin.include_role \
    --args name="$role" \
    localhost \
    -e state=$state
)
