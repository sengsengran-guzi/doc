#!/usr/bin/env bash
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
cd "$(dirname "$0")/../../.."
/opt/homebrew/bin/python3.11 -u doc/jp/_accept/snap-fault-injection.py
