#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pyinstaller --noconfirm --onefile --name wfmarket-cli cli.py
pyinstaller --noconfirm --onefile --name wfmarket-gui gui.py
