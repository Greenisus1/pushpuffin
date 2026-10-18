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
ensure_gh() {
 if command -v gh >/dev/null 2>&1; then return 0; fi
 if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = 0 ]; then
  echo 'GitHub CLI (gh) is missing. Installing from the official GitHub apt repo.'
  install -m 0755 -d /usr/share/keyrings || return 1
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
   -o /usr/share/keyrings/githubcli-archive-keyring.gpg || { echo 'Could not download the GitHub CLI repo key. Check network, then retry.'; return 1; }
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
   > /etc/apt/sources.list.d/github-cli.list
  apt-get update -qq || { echo 'apt-get update failed. Check apt sources/network, then retry.'; return 1; }
  apt-get install -y gh || { echo 'Could not install gh. Check apt sources/network, then retry.'; return 1; }
 else
  echo 'GitHub CLI (gh) is missing. Install it as root from https://cli.github.com/packages, then retry.'
  return 1
 fi
 command -v gh >/dev/null 2>&1 || { echo 'gh was installed but is still not on PATH. Check your apt installation.'; return 1; }
}
case "${1:-}" in
 install)
  ensure_gh || exit 1
  test -f "$HOME/.local/share/filefinderplus/terminal_browser.py" || { echo 'Install FileFinder+ first.'; exit 1; }
  python3 -c 'import pushpuffin; raise SystemExit(0 if pushpuffin.store_installed() else 1)' || { echo 'Install Pi App Store first: https://github.com/Greenisus1/pi-app-store'; exit 1; }
  ;;
 run) exec python3 pushpuffin.py ;;
 gui) ensure_tk; check_display; exec python3 pushpuffin.py --gui ;;
 *) echo 'Usage: bash app-store.sh install|run|gui'; exit 2 ;;
esac
