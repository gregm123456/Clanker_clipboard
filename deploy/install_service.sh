# Install systemd service for clanker-clipboard (Raspberry Pi Zero 2W)
# Run from the device as a user with sudo access.

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_FILE="$REPO_DIR/deploy/clanker-clipboard.service"
DEST="/etc/systemd/system/clanker-clipboard.service"

echo "Installing $SERVICE_FILE → $DEST"
sudo cp "$SERVICE_FILE" "$DEST"
sudo systemctl daemon-reload
sudo systemctl enable clanker-clipboard
sudo systemctl start clanker-clipboard
echo "Done. Check status with: sudo systemctl status clanker-clipboard"
