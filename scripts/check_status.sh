#!/usr/bin/env bash
# =============================================================================
# check_status.sh — Live status check for both Pi3 and Pi4
# =============================================================================
# Run from any machine on the same network:
#   bash check_status.sh [pi4_host]
#
# Default host: pi4.local  (or set PI4_HOST env variable)
# =============================================================================
set -euo pipefail

PI4_HOST="${1:-${PI4_HOST:-192.168.8.11}}"
PI4_PORT="${PI4_PORT:-5000}"
BASE_URL="http://${PI4_HOST}:${PI4_PORT}"
TIMEOUT=5

echo "========================================="
echo " 2pis Status Check"
echo " Pi4 address: ${PI4_HOST}:${PI4_PORT}"
echo "========================================="

# --- Ping test ---
echo ""
echo "[Network]"
if ping -c1 -W2 "${PI4_HOST}" &>/dev/null; then
    echo "  ✓ Pi4 is reachable on the network"
else
    echo "  ✗ Cannot ping ${PI4_HOST} — check network / hostname"
fi

# --- HTTP status endpoint ---
echo ""
echo "[Pi4 Server]"
if ! STATUS_JSON=$(curl -sf --max-time "${TIMEOUT}" "${BASE_URL}/status" 2>&1); then
    echo "  ✗ Server not responding at ${BASE_URL}/status"
    echo "    → Check: sudo systemctl status pi4-server"
    exit 1
fi

echo "  ✓ Server is up"

# Parse JSON with python3 (avoids jq dependency)
python3 - <<PYEOF
import json, sys
data = json.loads('''${STATUS_JSON}''')
print(f"  Frame count     : {data.get('frame_count', '?')}")
print(f"  Last frame      : {data.get('last_timestamp', 'none')}")
print(f"  Video exists    : {data.get('video_exists', False)}")
print(f"  Video size      : {data.get('video_size_mb', 0)} MB")
print(f"  USB mounted     : {data.get('usb_mounted', False)}")
print(f"  Rebuild running : {data.get('rebuild_in_progress', False)}")
print(f"  Pending rebuild : {data.get('frames_pending_rebuild', 0)} frames")
PYEOF

# --- Frame list ---
echo ""
echo "[Stored Frames]"
FRAMES_JSON=$(curl -sf --max-time "${TIMEOUT}" "${BASE_URL}/frames" 2>/dev/null || echo '{"count":0,"frames":[]}')
python3 - <<PYEOF
import json
data = json.loads('''${FRAMES_JSON}''')
count = data.get('count', 0)
frames = data.get('frames', [])
print(f"  Total frames stored: {count}")
if frames:
    print(f"  Oldest : {frames[0]}")
    print(f"  Newest : {frames[-1]}")
PYEOF

# --- Pi4 service status ---
echo ""
echo "[Services on Pi4]"
echo "  (run this on Pi4 for detailed service status):"
echo "    sudo systemctl status pi4-server pi4-player"
echo ""

# --- Trigger manual rebuild ---
read -rp "Trigger timelapse rebuild now? [y/N] " ANSWER
if [[ "${ANSWER,,}" == "y" ]]; then
    REBUILD=$(curl -sf --max-time 10 "${BASE_URL}/rebuild" 2>/dev/null || echo '{"status":"error"}')
    python3 -c "import json; d=json.loads('${REBUILD}'); print('  Result:', d.get('status','?'))"
fi

echo ""
echo "Done."
