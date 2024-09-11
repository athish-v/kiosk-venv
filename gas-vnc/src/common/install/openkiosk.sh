#!/usr/bin/env bash
### every exit != 0 fails the script
set -e

echo "Install OpenKiosk Browser"
apt-get install -y curl
curl -O -k https://www.mozdevgroup.com/dropbox/okcd/115/release/OpenKiosk115.12.0-2024-06-25-x86_64.deb
apt install -y ./OpenKiosk115.12.0-2024-06-25-x86_64.deb
apt-get clean -y
