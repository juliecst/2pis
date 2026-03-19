#!/usr/bin/env python3
"""
Pi4 — Frame Receiver & Timelapse Server
=========================================
HTTP server (Flask) that receives JPEG frames from Pi3, stores them on a USB
stick (or locally as fallback), and triggers a timelapse rebuild.

Endpoints
---------
POST /receive_frame   multipart: field "frame" (JPEG), field "timestamp" (str)
GET  /status          JSON: frame count, last timestamp, video path, USB status
GET  /frames          JSON: list of stored frame filenames
GET  /rebuild         Trigger an immediate timelapse rebuild (debug helper)

Usage:
    python3 server.py            # normal operation (binds 0.0.0.0:5000)
    python3 server.py --debug    # Flask debug mode — auto-reloads on code change
"""

import argparse
import logging
import logging.handlers
import os
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request

try:
    from config import (
        SERVER_HOST, SERVER_PORT,
        USB_MOUNT_POINT, USB_FRAMES_DIR, USB_VIDEO_PATH,
        LOCAL_FRAMES_DIR, LOCAL_VIDEO_PATH,
        REBUILD_EVERY_N,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )
    from timelapse import build_timelapse
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(__file__))
    from config import (
        SERVER_HOST, SERVER_PORT,
        USB_MOUNT_POINT, USB_FRAMES_DIR, USB_VIDEO_PATH,
        LOCAL_FRAMES_DIR, LOCAL_VIDEO_PATH,
        REBUILD_EVERY_N,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )
    from timelapse import build_timelapse


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("pi4-server")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        print(f"WARNING: cannot open log file {LOG_FILE}: {exc}", file=sys.stderr)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def is_usb_mounted() -> bool:
    """Return True if the USB stick mount point is available."""
    return os.path.ismount(USB_MOUNT_POINT)


def get_storage_paths() -> tuple[str, str]:
    """Return (frames_dir, video_path) — USB if available, otherwise local."""
    if is_usb_mounted():
        return USB_FRAMES_DIR, USB_VIDEO_PATH
    log.warning("USB stick not mounted at %s — using local storage.", USB_MOUNT_POINT)
    return LOCAL_FRAMES_DIR, LOCAL_VIDEO_PATH


def ensure_frames_dir(frames_dir: str) -> None:
    Path(frames_dir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_new_frames_since_rebuild: int = 0
_last_timestamp: str = ""
_rebuild_in_progress: bool = False


def _schedule_rebuild_if_needed(frames_dir: str, video_path: str) -> None:
    """Rebuild timelapse in a background thread if enough new frames have arrived."""
    global _new_frames_since_rebuild, _rebuild_in_progress

    threshold = REBUILD_EVERY_N if REBUILD_EVERY_N > 0 else 1

    with _state_lock:
        if _rebuild_in_progress:
            return
        if _new_frames_since_rebuild < threshold:
            return
        _rebuild_in_progress = True
        _new_frames_since_rebuild = 0

    def _do_rebuild():
        global _rebuild_in_progress
        try:
            build_timelapse(frames_dir, video_path, log)
        except Exception as exc:  # noqa: BLE001
            log.error("Timelapse rebuild failed: %s", exc)
        finally:
            with _state_lock:
                _rebuild_in_progress = False

    threading.Thread(target=_do_rebuild, daemon=True, name="timelapse-builder").start()


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/receive_frame", methods=["POST"])
def receive_frame():
    global _new_frames_since_rebuild, _last_timestamp

    if "frame" not in request.files:
        log.warning("Received request without 'frame' field")
        return jsonify({"error": "missing 'frame' field"}), 400

    file = request.files["frame"]
    timestamp = request.form.get("timestamp") or ""

    if not timestamp:
        # Fallback: use server time
        timestamp = time.strftime("%Y%m%d_%H%M%S")

    frames_dir, video_path = get_storage_paths()
    ensure_frames_dir(frames_dir)

    frame_path = os.path.join(frames_dir, f"{timestamp}.jpg")

    try:
        file.save(frame_path)
        log.info("Saved frame %s (%d bytes)", timestamp, os.path.getsize(frame_path))
    except OSError as exc:
        log.error("Cannot save frame %s: %s", timestamp, exc)
        return jsonify({"error": "storage error"}), 500

    with _state_lock:
        _new_frames_since_rebuild += 1
        _last_timestamp = timestamp

    _schedule_rebuild_if_needed(frames_dir, video_path)

    return jsonify({"status": "ok", "timestamp": timestamp}), 200


@app.route("/status", methods=["GET"])
def status():
    frames_dir, video_path = get_storage_paths()
    frame_count = 0
    if os.path.isdir(frames_dir):
        frame_count = len([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])

    video_exists = os.path.isfile(video_path)
    video_size_mb = (
        round(os.path.getsize(video_path) / 1024 / 1024, 2) if video_exists else 0
    )

    with _state_lock:
        last_ts = _last_timestamp
        rebuilding = _rebuild_in_progress
        pending = _new_frames_since_rebuild

    return jsonify({
        "status": "ok",
        "frame_count": frame_count,
        "last_timestamp": last_ts,
        "video_path": video_path,
        "video_exists": video_exists,
        "video_size_mb": video_size_mb,
        "usb_mounted": is_usb_mounted(),
        "rebuild_in_progress": rebuilding,
        "frames_pending_rebuild": pending,
    }), 200


@app.route("/frames", methods=["GET"])
def list_frames():
    frames_dir, _ = get_storage_paths()
    if not os.path.isdir(frames_dir):
        return jsonify({"frames": []}), 200
    frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    return jsonify({"frames": frames, "count": len(frames)}), 200


@app.route("/rebuild", methods=["GET"])
def trigger_rebuild():
    """Force an immediate timelapse rebuild (useful for debugging)."""
    global _new_frames_since_rebuild
    frames_dir, video_path = get_storage_paths()

    with _state_lock:
        _new_frames_since_rebuild = max(_new_frames_since_rebuild, REBUILD_EVERY_N or 1)

    _schedule_rebuild_if_needed(frames_dir, video_path)
    return jsonify({"status": "rebuild triggered"}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Pi4 frame receiver server.")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    args = parser.parse_args()

    log.info("Pi4 server starting on %s:%d", SERVER_HOST, SERVER_PORT)
    log.info("USB mounted: %s", is_usb_mounted())
    frames_dir, video_path = get_storage_paths()
    log.info("Frames dir : %s", frames_dir)
    log.info("Video path : %s", video_path)

    # If we already have frames from a previous session, rebuild the video
    if os.path.isdir(frames_dir):
        existing = [f for f in os.listdir(frames_dir) if f.endswith(".jpg")]
        if existing and not os.path.isfile(video_path):
            log.info(
                "Found %d existing frames without a video — rebuilding on startup.",
                len(existing),
            )
            try:
                build_timelapse(frames_dir, video_path, log)
            except Exception as exc:  # noqa: BLE001
                log.error("Startup rebuild failed: %s", exc)

    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
