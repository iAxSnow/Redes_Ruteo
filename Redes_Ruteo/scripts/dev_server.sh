#!/usr/bin/env bash
set -euo pipefail
cd site
python -m http.server 8000
