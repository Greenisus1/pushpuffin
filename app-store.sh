#!/bin/bash
# pi-app-store: 1
set -eu
cd -- "$(dirname -- "$0")"
case "${1:-}" in
 install)
  python3 -c 'import tkinter' || { echo 'Install python3-tk and use a desktop or VNC.'; exit 1; }
  command -v gh >/dev/null || { echo 'Install the official GitHub CLI (gh).'; exit 1; }
  test -f "$HOME/.local/share/filefinderplus/filefinderplus.py" || { echo 'Install FileFinder+ first.'; exit 1; }
  python3 -c 'import pushpuffin; raise SystemExit(0 if pushpuffin.store_installed() else 1)' || { echo 'Install Pi App Store first: https://github.com/Greenisus1/pi-app-store'; exit 1; }
  ;;
 run) exec python3 pushpuffin.py ;;
 *) echo 'Usage: bash app-store.sh install|run'; exit 2 ;;
esac
