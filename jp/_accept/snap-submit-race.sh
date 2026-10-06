#!/usr/bin/env bash
set -euo pipefail
export PATH=/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/../../.."
python3 doc/jp/_accept/snap-submit-race.py
