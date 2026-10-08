#!/bin/bash
# pi-app-store: 1
set -eu
cd -- "$(dirname -- "$0")"
ensure_tk() {
 if python3 -c 'import tkinter' >/dev/null 2>&1; then return 0; fi
 if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = 0 ]; then
  echo 'Tk is missing. Installing python3-tk with apt-get.'
  apt-get install -y python3-tk || { echo 'Could not install python3-tk. Check apt sources/network, then retry.'; return 1; }
 else
  echo 'Tk is missing. Install python3-tk as root using apt, then retry. A desktop or VNC is needed to run this app.'
  return 1
 fi
 python3 -c 'import tkinter' >/dev/null 2>&1 || { echo 'python3-tk was installed but this Python still cannot load Tk. Check your Python installation.'; return 1; }
}
check_display() {
 if [ -z "${DISPLAY:-}" ]; then
  echo 'No desktop display is available. Open a desktop or VNC session and run this app there (DISPLAY must be set).'
  return 1
 fi
 python3 -c 'import tkinter as tk; r=tk.Tk(); r.withdraw(); r.destroy()' >/dev/null 2>&1 || {
  echo 'Cannot open the desktop display. Use a working desktop or VNC session and install python3-tk if missing.'
  return 1
 }
}
case "${1:-}" in
 install)
  ensure_tk
  command -v gh >/dev/null || { echo 'Install the official GitHub CLI (gh).'; exit 1; }
  test -f "$HOME/.local/share/filefinderplus/filefinderplus.py" || { echo 'Install FileFinder+ first.'; exit 1; }
  python3 -c 'import pushpuffin; raise SystemExit(0 if pushpuffin.store_installed() else 1)' || { echo 'Install Pi App Store first: https://github.com/Greenisus1/pi-app-store'; exit 1; }
  ;;
 run) check_display; exec python3 pushpuffin.py ;;
 *) echo 'Usage: bash app-store.sh install|run'; exit 2 ;;
esac
