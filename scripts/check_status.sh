#!/usr/bin/env bash
# =============================================================================
# check_status.sh — Live status check for both Pi1 and Pi5
# =============================================================================
# Run from any machine on the same network:
#   bash check_status.sh [pi5_host]
#
# Default host: pi5.local  (or set PI5_HOST env variable)
# =============================================================================
set -euo pipefail

PI5_HOST="${1:-${PI5_HOST:-192.168.8.11}}"
PI5_PORT="${PI5_PORT:-5000}"
BASE_URL="http://${PI5_HOST}:${PI5_PORT}"
TIMEOUT=5

echo "========================================="
echo " 2pis Status Check"
echo " Pi5 address: ${PI5_HOST}:${PI5_PORT}"
echo "========================================="

# --- Ping test ---
echo ""
echo "[Network]"
if ping -c1 -W2 "${PI5_HOST}" &>/dev/null; then
    echo "  ✓ Pi5 is reachable on the network"
else
    echo "  ✗ Cannot ping ${PI5_HOST} — check network / hostname"
fi

# --- HTTP status endpoint ---
echo ""
echo "[Pi5 Server]"
if ! STATUS_JSON=$(curl -sf --max-time "${TIMEOUT}" "${BASE_URL}/status" 2>&1); then
    echo "  ✗ Server not responding at ${BASE_URL}/status"
    echo "    → Check: sudo systemctl status pi5-server"
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

# --- Pi5 service status ---
echo ""
echo "[Services on Pi5]"
echo "  (run this on Pi5 for detailed service status):"
echo "    sudo systemctl status pi5-server pi5-player"
echo ""

# --- Trigger manual rebuild ---
read -rp "Trigger timelapse rebuild now? [y/N] " ANSWER
if [[ "${ANSWER,,}" == "y" ]]; then
    REBUILD=$(curl -sf --max-time 10 "${BASE_URL}/rebuild" 2>/dev/null || echo '{"status":"error"}')
    python3 -c "import json; d=json.loads('${REBUILD}'); print('  Result:', d.get('status','?'))"
fi

echo ""
echo "Done."
