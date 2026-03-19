#!/usr/bin/env bash
# =============================================================================
# mount_usb.sh — Mount the TIMELAPSE USB stick and verify it is writable
# =============================================================================
# Usage (run on Pi5):
#   bash mount_usb.sh [device]     e.g.  bash mount_usb.sh /dev/sda1
#
# If no device is given the script tries to find one automatically by label.
# =============================================================================
set -euo pipefail

USB_LABEL="TIMELAPSE"
MOUNT_POINT="/media/pi/${USB_LABEL}"
DEVICE="${1:-}"

echo "===  USB Mount Helper  ==="

# --- Auto-detect device by label ---
if [[ -z "${DEVICE}" ]]; then
    DEVICE=$(blkid -L "${USB_LABEL}" 2>/dev/null || true)
    if [[ -z "${DEVICE}" ]]; then
        echo "ERROR: No device with label '${USB_LABEL}' found."
        echo ""
        echo "Available block devices:"
        lsblk -o NAME,FSTYPE,LABEL,SIZE,MOUNTPOINT
        echo ""
        echo "Tips:"
        echo "  • Format your USB stick as FAT32 or exFAT."
        echo "  • Label it '${USB_LABEL}' (case-sensitive)."
        echo "  • Or run:  bash mount_usb.sh /dev/sdXN"
        exit 1
    fi
    echo "Found device: ${DEVICE}"
fi

# --- Create mount point ---
sudo mkdir -p "${MOUNT_POINT}"

# --- Mount ---
if mountpoint -q "${MOUNT_POINT}"; then
    echo "Already mounted at ${MOUNT_POINT}"
else
    sudo mount -o uid=pi,gid=pi "${DEVICE}" "${MOUNT_POINT}"
    echo "Mounted ${DEVICE} → ${MOUNT_POINT}"
fi

# --- Verify writable ---
TEST_FILE="${MOUNT_POINT}/.write_test_$$"
if touch "${TEST_FILE}" 2>/dev/null; then
    rm -f "${TEST_FILE}"
    echo "USB stick is writable ✓"
else
    echo "ERROR: USB stick is mounted but NOT writable."
    echo "Check filesystem and permissions."
    exit 1
fi

# --- Show free space ---
echo ""
df -h "${MOUNT_POINT}"
echo ""
echo "USB stick ready.  Restart the pi5-server service if it is already running:"
echo "  sudo systemctl restart pi5-server"
