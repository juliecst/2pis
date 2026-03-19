#!/usr/bin/env bash
# =============================================================================
# setup_pi3.sh — One-time setup for the Raspberry Pi 3 (camera node)
# =============================================================================
# Run as: bash setup_pi3.sh
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="pi3-camera"
SERVICE_FILE="${REPO_DIR}/systemd/${SERVICE_NAME}.service"
INSTALL_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "===  Pi3 Setup ==="
echo "Repo: ${REPO_DIR}"

# --- 1. System dependencies ---
echo "[1/4] Installing system dependencies…"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-pip \
    python3-requests \
    python3-picamera2 \
    libcamera-apps

# Pillow + numpy for the mock frame generator (also useful for real frames)
pip3 install --break-system-packages --quiet pillow numpy 2>/dev/null \
    || pip3 install --quiet pillow numpy

# --- 2. Enable camera interface ---
echo "[2/4] Enabling camera interface…"
if command -v raspi-config &>/dev/null; then
    sudo raspi-config nonint do_camera 0
    echo "      Camera interface enabled."
else
    echo "      WARNING: raspi-config not found — enable the camera manually."
fi

# --- 3. Install systemd service ---
echo "[3/4] Installing systemd service…"
sudo cp "${SERVICE_FILE}" "${INSTALL_PATH}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
echo "      Service '${SERVICE_NAME}' enabled."

# --- 4. Connectivity test ---
echo "[4/4] Quick self-test (dry-run capture)…"
cd "${REPO_DIR}/pi3"
python3 camera.py --dry-run && echo "      Camera OK." || echo "      Camera check failed — check hardware connections."

echo ""
echo "Setup complete!  Reboot to start capturing automatically."
echo "  Start now   : sudo systemctl start ${SERVICE_NAME}"
echo "  View logs   : sudo journalctl -u ${SERVICE_NAME} -f"
echo "  Test send   : cd ${REPO_DIR}/pi3 && python3 camera.py --test"
