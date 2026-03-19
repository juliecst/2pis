#!/usr/bin/env python3
"""
Pi3 — Camera Capture and Send
==============================
Captures JPEG frames from the Raspberry Pi HQ Camera at a fixed interval
and sends each frame to the Pi4 receiver via a simple HTTP POST request.

Designed to be:
  - Robust: retries on network failure, never crashes permanently
  - Simple: no Samba, no shared filesystems — just HTTP
  - Persistent: resumes automatically when Pi3 is rebooted

Usage:
    python3 camera.py            # normal operation
    python3 camera.py --test     # send a single test frame and exit
    python3 camera.py --dry-run  # capture but do not send (for camera testing)
"""

import argparse
import io
import logging
import logging.handlers
import sys
import time
from datetime import datetime

import requests

try:
    from config import (
        PI4_HOST, PI4_PORT, PI4_RECEIVE_ENDPOINT,
        CAPTURE_INTERVAL, RESOLUTION, JPEG_QUALITY,
        MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )
except ModuleNotFoundError:
    # Allow running from a different working directory
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config import (
        PI4_HOST, PI4_PORT, PI4_RECEIVE_ENDPOINT,
        CAPTURE_INTERVAL, RESOLUTION, JPEG_QUALITY,
        MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("pi3-camera")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Rotating file handler
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        print(f"WARNING: cannot open log file {LOG_FILE}: {exc}", file=sys.stderr)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
# Camera abstraction
# ---------------------------------------------------------------------------

def _open_camera_picamera2():
    """Open camera with picamera2 (Pi OS Bullseye / Bookworm)."""
    from picamera2 import Picamera2  # type: ignore
    cam = Picamera2()
    config = cam.create_still_configuration(
        main={"size": RESOLUTION, "format": "RGB888"}
    )
    cam.configure(config)
    cam.start()
    time.sleep(2)  # warm-up
    log.info("Camera opened via picamera2 at resolution %s", RESOLUTION)
    return cam, "picamera2"


def _open_camera_picamera():
    """Open camera with legacy picamera (Pi OS Buster)."""
    import picamera  # type: ignore
    cam = picamera.PiCamera()
    cam.resolution = RESOLUTION
    time.sleep(2)
    log.info("Camera opened via picamera at resolution %s", RESOLUTION)
    return cam, "picamera"


def open_camera():
    """Try picamera2 first, fall back to picamera, then mock."""
    try:
        return _open_camera_picamera2()
    except Exception as exc:
        log.warning("picamera2 not available (%s), trying legacy picamera", exc)

    try:
        return _open_camera_picamera()
    except Exception as exc:
        log.warning("picamera not available (%s), using mock camera", exc)

    log.warning("No real camera found — using mock camera (grey gradient image).")
    return None, "mock"


def capture_frame(camera, lib: str) -> bytes:
    """Capture a single JPEG frame and return it as bytes."""
    buf = io.BytesIO()

    if lib == "picamera2":
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        array = camera.capture_array()
        img = Image.fromarray(array)
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)

    elif lib == "picamera":
        camera.capture(buf, format="jpeg", quality=JPEG_QUALITY)

    else:  # mock
        _generate_mock_frame(buf)

    buf.seek(0)
    return buf.read()


def _generate_mock_frame(buf: io.BytesIO) -> None:
    """Generate a simple gradient JPEG for testing without a real camera."""
    try:
        import numpy as np  # type: ignore
        from PIL import Image, ImageDraw, ImageFont  # type: ignore

        w, h = RESOLUTION
        # Gradient background
        img = Image.fromarray(
            np.tile(
                np.linspace(30, 180, w, dtype="uint8"), (h, 1)
            )
            .reshape(h, w, 1)
            .repeat(3, axis=2)
        )
        draw = ImageDraw.Draw(img)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, 10), f"MOCK FRAME\n{ts}", fill=(255, 255, 255))
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    except ImportError:
        # Minimal valid 1×1 JPEG if Pillow is not installed
        buf.write(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),\x01\x02\x02\x02"
            b"\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02"
            b"\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02"
            b"\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02"
            b"\x02\x02\x02\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11"
            b"\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07"
            b"\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04"
            b"\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05"
            b"\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R"
            b"\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ"
            b"STUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92"
            b"\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8"
            b"\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1"
            b"\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6"
            b"\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd4"
            b"P\x00\x00\x00\x00\x1f\xff\xd9"
        )


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

PI4_URL = f"http://{PI4_HOST}:{PI4_PORT}{PI4_RECEIVE_ENDPOINT}"


def send_frame(frame_bytes: bytes, timestamp: str) -> bool:
    """Send a JPEG frame to Pi4.  Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                PI4_URL,
                files={"frame": (f"{timestamp}.jpg", frame_bytes, "image/jpeg")},
                data={"timestamp": timestamp},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                log.info("Frame %s sent successfully (attempt %d)", timestamp, attempt)
                return True
            log.warning(
                "Pi4 returned HTTP %d for frame %s (attempt %d/%d)",
                resp.status_code, timestamp, attempt, MAX_RETRIES,
            )
        except requests.exceptions.ConnectionError:
            log.warning(
                "Cannot reach Pi4 at %s (attempt %d/%d) — is it running?",
                PI4_URL, attempt, MAX_RETRIES,
            )
        except requests.exceptions.Timeout:
            log.warning(
                "Request timed out (attempt %d/%d)", attempt, MAX_RETRIES
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Unexpected error sending frame: %s", exc)

        if attempt < MAX_RETRIES:
            log.info("Retrying in %d seconds…", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    log.error("Failed to send frame %s after %d attempts.", timestamp, MAX_RETRIES)
    return False


def check_pi4_reachable() -> bool:
    """Quick connectivity check before starting the capture loop."""
    url = f"http://{PI4_HOST}:{PI4_PORT}/status"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_capture_loop(camera, lib: str) -> None:
    log.info("Starting capture loop — interval %ds, sending to %s", CAPTURE_INTERVAL, PI4_URL)

    if not check_pi4_reachable():
        log.warning(
            "Pi4 not reachable at startup.  Frames will be retried when it comes online."
        )

    while True:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            frame_bytes = capture_frame(camera, lib)
            log.debug("Captured %d bytes for frame %s", len(frame_bytes), timestamp)
        except Exception as exc:  # noqa: BLE001
            log.error("Capture failed: %s — skipping frame", exc)
            time.sleep(CAPTURE_INTERVAL)
            continue

        send_frame(frame_bytes, timestamp)
        time.sleep(CAPTURE_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi3 camera capture and send.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Capture and send a single frame, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Capture frames but do NOT send them (camera test only).",
    )
    args = parser.parse_args()

    camera, lib = open_camera()
    log.info("Camera library: %s", lib)

    if args.dry_run:
        log.info("--dry-run: capturing one frame (not sending)…")
        data = capture_frame(camera, lib)
        log.info("Captured %d bytes — camera is working.", len(data))
        return

    if args.test:
        log.info("--test: capturing and sending one frame…")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = capture_frame(camera, lib)
        ok = send_frame(data, timestamp)
        sys.exit(0 if ok else 1)

    try:
        run_capture_loop(camera, lib)
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down.")


if __name__ == "__main__":
    main()
