#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
python3 rebuild_conversations.py
