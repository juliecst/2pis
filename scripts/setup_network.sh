#!/usr/bin/env bash
# =============================================================================
# setup_network.sh — Configure WiFi and static IP for the museum network
# =============================================================================
# Run on each Pi:
#   sudo bash setup_network.sh
#
# This script:
#   1. Connects to the museum WiFi (Goodlife — GL-net Mango router)
#   2. Assigns a static IP based on the hostname:
#        pi3 → 192.168.8.10
#        pi4 → 192.168.8.11
#
# Works with both NetworkManager (Pi OS Bookworm) and dhcpcd (Buster / Bullseye).
# =============================================================================
set -euo pipefail

# --- Museum network settings ---
SSID="Goodlife"
PASS="Goodlife"
GATEWAY="192.168.8.1"
DNS="8.8.8.8 8.8.4.4"
SUBNET="/24"

# --- Determine static IP from hostname ---
HOSTNAME=$(hostname)
case "${HOSTNAME}" in
    pi3) STATIC_IP="192.168.8.10" ;;
    pi4) STATIC_IP="192.168.8.11" ;;
    *)
        echo "ERROR: Unrecognized hostname '${HOSTNAME}'."
        echo "       Expected 'pi3' or 'pi4'. Set the hostname first:"
        echo "         sudo hostnamectl set-hostname pi3   # or pi4"
        exit 1
        ;;
esac

echo "===  Museum Network Setup  ==="
echo "Hostname : ${HOSTNAME}"
echo "SSID     : ${SSID}"
echo "Static IP: ${STATIC_IP}"
echo "Gateway  : ${GATEWAY}"
echo ""

# =============================================================================
# Detect network manager
# =============================================================================
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    NETWORK_MGMT="NetworkManager"
elif command -v dhcpcd &>/dev/null || [ -f /etc/dhcpcd.conf ]; then
    NETWORK_MGMT="dhcpcd"
else
    echo "WARNING: Could not detect network manager. Trying dhcpcd method."
    NETWORK_MGMT="dhcpcd"
fi
echo "Detected: ${NETWORK_MGMT}"
echo ""

# =============================================================================
# NetworkManager (Bookworm)
# =============================================================================
if [[ "${NETWORK_MGMT}" == "NetworkManager" ]]; then
    echo "[1/2] Connecting to WiFi '${SSID}'…"
    nmcli connection delete "${SSID}" 2>/dev/null || true
    nmcli device wifi connect "${SSID}" password "${PASS}"

    echo "[2/2] Assigning static IP ${STATIC_IP}…"
    nmcli connection modify "${SSID}" \
        ipv4.method manual \
        ipv4.addresses "${STATIC_IP}${SUBNET}" \
        ipv4.gateway "${GATEWAY}" \
        ipv4.dns "${DNS// /,}"
    nmcli connection up "${SSID}"

    echo ""
    echo "Done!  Verify with: nmcli device show wlan0"
    exit 0
fi

# =============================================================================
# dhcpcd (Buster / Bullseye)
# =============================================================================
DHCPCD_CONF="/etc/dhcpcd.conf"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"

# --- WiFi credentials ---
echo "[1/2] Adding WiFi network '${SSID}'…"
if [ -f "${WPA_CONF}" ]; then
    BACKUP="${WPA_CONF}.backup_$(date +%Y%m%d_%H%M%S)"
    sudo cp "${WPA_CONF}" "${BACKUP}"
    echo "       Backup saved to ${BACKUP}"
fi

# Remove any existing block for this SSID to avoid duplicates
sudo sed -i "/# Museum WiFi (Goodlife)/,/^}/d" "${WPA_CONF}" 2>/dev/null || true

PSK=$(wpa_passphrase "${SSID}" "${PASS}" | grep -E "^\s+psk=" | tail -1 | tr -d '[:space:]')

cat <<EOF | sudo tee -a "${WPA_CONF}" > /dev/null

# Museum WiFi (Goodlife)
network={
    ssid="${SSID}"
    ${PSK}
    priority=10
    key_mgmt=WPA-PSK
}
EOF
echo "       Network '${SSID}' added."

# --- Static IP ---
echo "[2/2] Assigning static IP ${STATIC_IP}…"
if [ -f "${DHCPCD_CONF}" ]; then
    BACKUP="${DHCPCD_CONF}.backup_$(date +%Y%m%d_%H%M%S)"
    sudo cp "${DHCPCD_CONF}" "${BACKUP}"
    echo "       Backup saved to ${BACKUP}"
fi

# Remove any existing static block for wlan0 to avoid duplicates
sudo sed -i "/# Static IP for museum network/,/^$/d" "${DHCPCD_CONF}" 2>/dev/null || true

cat <<EOF | sudo tee -a "${DHCPCD_CONF}" > /dev/null

# Static IP for museum network
interface wlan0
static ip_address=${STATIC_IP}${SUBNET}
static routers=${GATEWAY}
static domain_name_servers=${DNS}
EOF
echo "       Static IP configured in ${DHCPCD_CONF}"

# Apply without reboot if possible
sudo wpa_cli -i wlan0 reconfigure 2>/dev/null && echo "       WiFi reconfigured." \
    || echo "       WiFi will apply on next reboot."

echo ""
echo "Done!  Reboot to apply all changes:"
echo "  sudo reboot"
echo ""
echo "After reboot, verify with:"
echo "  ip addr show wlan0"
echo "  ping -c1 ${GATEWAY}"
echo "  ping -c1 8.8.8.8       # internet connectivity"
