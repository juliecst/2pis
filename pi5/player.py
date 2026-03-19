#!/usr/bin/env python3
"""
Pi5 — Video Player
===================
Plays the timelapse video on loop on the Waveshare 5-inch display (800×480).
When a new timelapse is built, mpv is restarted at the next loop so it picks
up the freshly written file.

Usage:
    python3 player.py            # normal operation
    python3 player.py --debug    # verbose output, no fullscreen
"""

import argparse
import logging
import os
import subprocess
import sys
import time

try:
    from config import (
        USB_VIDEO_PATH, LOCAL_VIDEO_PATH,
        USB_MOUNT_POINT,
        DISPLAY_WIDTH, DISPLAY_HEIGHT,
        MPV_EXTRA_OPTS,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(__file__))
    from config import (
        USB_VIDEO_PATH, LOCAL_VIDEO_PATH,
        USB_MOUNT_POINT,
        DISPLAY_WIDTH, DISPLAY_HEIGHT,
        MPV_EXTRA_OPTS,
        LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    )

import logging.handlers

POLL_INTERVAL   = 5    # seconds to wait between checks when no video exists
RESTART_DELAY   = 1    # seconds to wait between mpv restarts
WAIT_FOR_VIDEO  = 10   # seconds to wait before first retry if no video found


def setup_logging(debug: bool) -> logging.Logger:
    logger = logging.getLogger("pi5-player")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    try:
        import logging.handlers as _lh
        fh = _lh.RotatingFileHandler(
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


def resolve_video_path() -> str | None:
    """Return path to the timelapse video, preferring USB storage."""
    if os.path.ismount(USB_MOUNT_POINT) and os.path.isfile(USB_VIDEO_PATH):
        return USB_VIDEO_PATH
    if os.path.isfile(LOCAL_VIDEO_PATH):
        return LOCAL_VIDEO_PATH
    return None


def get_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def build_mpv_command(video_path: str, fullscreen: bool) -> list[str]:
    cmd = ["mpv"]
    if fullscreen:
        cmd += [
            "--fullscreen",
            f"--geometry={DISPLAY_WIDTH}x{DISPLAY_HEIGHT}",
        ]
    cmd += [
        "--loop=inf",
        "--no-terminal",
        "--really-quiet",
    ]
    if MPV_EXTRA_OPTS:
        cmd += MPV_EXTRA_OPTS.split()
    cmd.append(video_path)
    return cmd


def run_player(debug: bool = False) -> None:
    log = setup_logging(debug)
    fullscreen = not debug

    log.info(
        "Player starting — display %dx%d, fullscreen=%s",
        DISPLAY_WIDTH, DISPLAY_HEIGHT, fullscreen,
    )

    current_video: str | None = None
    current_mtime: float = 0.0
    proc: subprocess.Popen | None = None

    while True:
        video_path = resolve_video_path()

        if video_path is None:
            log.info("No timelapse video found yet — waiting %ds…", WAIT_FOR_VIDEO)
            if proc is not None:
                proc.terminate()
                proc = None
            time.sleep(WAIT_FOR_VIDEO)
            continue

        new_mtime = get_mtime(video_path)
        video_changed = (video_path != current_video) or (new_mtime > current_mtime)

        # Kill mpv if the video was updated or it exited on its own
        if proc is not None:
            proc_exited = proc.poll() is not None
            if video_changed or proc_exited:
                if video_changed:
                    log.info("Video updated — restarting player.")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                proc = None
                time.sleep(RESTART_DELAY)

        # Start (or restart) mpv
        if proc is None:
            cmd = build_mpv_command(video_path, fullscreen)
            log.info("Launching mpv: %s", " ".join(cmd))
            try:
                proc = subprocess.Popen(cmd)
                current_video = video_path
                current_mtime = new_mtime
            except FileNotFoundError:
                log.error("mpv not found — install with: sudo apt install mpv")
                time.sleep(30)
                continue

        time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi5 timelapse video player.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Verbose logging; disable fullscreen for desktop testing.",
    )
    args = parser.parse_args()

    try:
        run_player(debug=args.debug)
    except KeyboardInterrupt:
        print("\nPlayer stopped.")


if __name__ == "__main__":
    main()
