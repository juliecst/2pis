#!/usr/bin/env bash
# =============================================================================
# switch_wifi.sh — Switch Pi1 or Pi5 back to normal (home/office) WiFi
# =============================================================================
# Usage:
#   bash switch_wifi.sh                    # interactive
#   bash switch_wifi.sh "MySSID" "MyPass"  # non-interactive
#
# Works with both wpa_supplicant (Raspberry Pi OS Buster / Bullseye) and
# NetworkManager (Bookworm).
# =============================================================================
set -euo pipefail

SSID="${1:-}"
PASS="${2:-}"
BACKUP_SUFFIX=".backup_$(date +%Y%m%d_%H%M%S)"

echo "===  WiFi Configuration Tool  ==="
echo ""

# --- Detect network manager ---
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    NETWORK_MGMT="NetworkManager"
elif systemctl is-active --quiet wpa_supplicant 2>/dev/null; then
    NETWORK_MGMT="wpa_supplicant"
else
    echo "WARNING: Could not detect network manager.  Trying wpa_supplicant method."
    NETWORK_MGMT="wpa_supplicant"
fi
echo "Detected: ${NETWORK_MGMT}"
echo ""

# --- Get SSID / password if not provided ---
if [[ -z "${SSID}" ]]; then
    read -rp "WiFi SSID (network name): " SSID
fi
if [[ -z "${PASS}" ]]; then
    read -rsp "WiFi password (hidden): " PASS
    echo ""
fi

if [[ -z "${SSID}" ]]; then
    echo "ERROR: SSID cannot be empty."
    exit 1
fi

# =============================================================================
# NetworkManager (Bookworm)
# =============================================================================
if [[ "${NETWORK_MGMT}" == "NetworkManager" ]]; then
    echo "Adding WiFi network '${SSID}' via nmcli…"
    # Remove existing connection with same name if present
    nmcli connection delete "${SSID}" 2>/dev/null || true
    nmcli device wifi connect "${SSID}" password "${PASS}"
    echo ""
    echo "Connected!  Use 'nmcli device' to verify."
    exit 0
fi

# =============================================================================
# wpa_supplicant (Buster / Bullseye)
# =============================================================================
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
echo "Updating ${WPA_CONF}…"

# Backup current config
sudo cp "${WPA_CONF}" "${WPA_CONF}${BACKUP_SUFFIX}"
echo "Backup saved to ${WPA_CONF}${BACKUP_SUFFIX}"

# Generate PSK
PSK=$(wpa_passphrase "${SSID}" "${PASS}" | grep "psk=" | tail -1 | tr -d ' ')

# Append new network block with high priority
cat <<EOF | sudo tee -a "${WPA_CONF}" > /dev/null

# Added by switch_wifi.sh on $(date)
network={
    ssid="${SSID}"
    ${PSK}
    priority=10
    key_mgmt=WPA-PSK
}
EOF

echo "Network '${SSID}' added with priority 10."

# Reconfigure wpa_supplicant without reboot
sudo wpa_cli -i wlan0 reconfigure 2>/dev/null && echo "wpa_cli reconfigure done." \
    || echo "wpa_cli not available — network will apply on next reboot."

echo ""
echo "If the connection does not appear immediately, run:"
echo "  sudo systemctl restart networking"
echo "  # or reboot"
echo ""
echo "To revert: sudo cp '${WPA_CONF}${BACKUP_SUFFIX}' '${WPA_CONF}'"
