#!/usr/bin/env bash
# =============================================================================
# setup_pi4.sh — One-time setup for the Raspberry Pi 4 (display / server node)
# =============================================================================
# Run as: bash setup_pi4.sh
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USB_LABEL="TIMELAPSE"
USB_MOUNT="/media/pi/${USB_LABEL}"

echo "===  Pi4 Setup ==="
echo "Repo: ${REPO_DIR}"

# --- 1. System dependencies ---
echo "[1/5] Installing system dependencies…"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-pip \
    python3-flask \
    ffmpeg \
    mpv \
    avahi-daemon

pip3 install --break-system-packages --quiet flask pillow numpy 2>/dev/null \
    || pip3 install --quiet flask pillow numpy

# --- 2. Enable avahi (mDNS so Pi3 can reach pi4.local) ---
echo "[2/5] Enabling avahi mDNS…"
sudo systemctl enable --now avahi-daemon
echo "      Pi4 will be discoverable as 'pi4.local' on the local network."

# --- 3. USB stick auto-mount ---
echo "[3/5] Configuring USB auto-mount for label '${USB_LABEL}'…"
sudo mkdir -p "${USB_MOUNT}"

# Add udev rule for auto-mount by label
UDEV_RULE="/etc/udev/rules.d/99-timelapse-usb.rules"
cat <<EOF | sudo tee "${UDEV_RULE}" > /dev/null
ACTION=="add", KERNEL=="sd[b-z][0-9]", ENV{ID_FS_LABEL}=="${USB_LABEL}", \
    RUN+="/bin/mount -o uid=pi,gid=pi /dev/%k ${USB_MOUNT}"
ACTION=="remove", KERNEL=="sd[b-z][0-9]", ENV{ID_FS_LABEL}=="${USB_LABEL}", \
    RUN+="/bin/umount ${USB_MOUNT}"
EOF
sudo udevadm control --reload-rules
echo "      udev rule installed at ${UDEV_RULE}"
echo "      Format your USB stick as FAT32 or exFAT and label it '${USB_LABEL}'."

# --- 4. Install systemd services ---
echo "[4/5] Installing systemd services…"
for svc in pi4-server pi4-player; do
    src="${REPO_DIR}/systemd/${svc}.service"
    dst="/etc/systemd/system/${svc}.service"
    sudo cp "${src}" "${dst}"
    sudo systemctl daemon-reload
    sudo systemctl enable "${svc}"
    echo "      Service '${svc}' enabled."
done

# --- 5. Run offline tests ---
echo "[5/5] Running offline tests…"
cd "${REPO_DIR}/pi4"
python3 -m pytest test_server.py -v --tb=short 2>/dev/null \
    || python3 test_server.py

echo ""
echo "Setup complete!  Reboot to start automatically."
echo "  Start server  : sudo systemctl start pi4-server"
echo "  Start player  : sudo systemctl start pi4-player"
echo "  Check status  : bash ${REPO_DIR}/scripts/check_status.sh"
echo "  View logs     : sudo journalctl -u pi4-server -f"
