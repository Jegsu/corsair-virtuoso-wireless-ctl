#!/bin/sh
# Installs corsairvirtuosoctl to ~/.local/bin, its man page, and the udev rule (needs sudo).
set -e
cd "$(dirname "$0")"
install -Dm755 corsairvirtuosoctl.py "$HOME/.local/bin/corsairvirtuosoctl"
install -Dm644 corsairvirtuosoctl.1 "$HOME/.local/share/man/man1/corsairvirtuosoctl.1"
sudo install -Dm644 70-corsair-headset.rules /etc/udev/rules.d/70-corsair-headset.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
echo "Installed. Try: corsairvirtuosoctl status, or: man corsairvirtuosoctl"
