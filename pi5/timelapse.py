#!/usr/bin/env python3
"""
Timelapse Builder
=================
Assembles all JPEG frames in *frames_dir* into an MP4 timelapse video using
ffmpeg.  The video is written to a temporary file first, then atomically
renamed to the final path so the player always sees a complete file.

Usage (standalone):
    python3 timelapse.py <frames_dir> <output_video>
"""

import glob
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from config import TIMELAPSE_FPS, TEMP_VIDEO_SUFFIX
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(__file__))
    from config import TIMELAPSE_FPS, TEMP_VIDEO_SUFFIX


def build_timelapse(
    frames_dir: str,
    output_video: str,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Build a timelapse MP4 from all JPEG frames in *frames_dir*.

    Parameters
    ----------
    frames_dir:    directory that contains the .jpg files
    output_video:  full path of the resulting .mp4
    logger:        optional logger; falls back to print()

    Returns True on success, False on failure.
    """
    log = logger or logging.getLogger("timelapse")

    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
    if not frames:
        log.warning("No JPEG frames found in %s — skipping build.", frames_dir)
        return False

    log.info("Building timelapse from %d frames → %s", len(frames), output_video)

    # Ensure the output directory exists
    Path(output_video).parent.mkdir(parents=True, exist_ok=True)

    # Write a concat list to a temp file
    tmp_list = None
    tmp_video = output_video + TEMP_VIDEO_SUFFIX
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="timelapse_list_"
        ) as f:
            tmp_list = f.name
            for frame_path in frames:
                # Each frame shown for 1/FPS seconds
                f.write(f"file '{frame_path}'\n")
                f.write(f"duration {1 / TIMELAPSE_FPS:.6f}\n")
            # ffmpeg concat demuxer requires the last entry without duration
            f.write(f"file '{frames[-1]}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", tmp_list,
            "-vf", f"scale={_display_size()}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-r", str(TIMELAPSE_FPS),
            tmp_video,
        ]
        log.debug("ffmpeg command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,   # 5-minute hard limit
        )

        if result.returncode != 0:
            log.error(
                "ffmpeg failed (exit %d):\n%s",
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
            _cleanup(tmp_video)
            return False

        # Atomic rename: replace old video only after successful build
        os.replace(tmp_video, output_video)
        size_mb = round(os.path.getsize(output_video) / 1024 / 1024, 2)
        log.info("Timelapse saved to %s (%.2f MB)", output_video, size_mb)
        return True

    except subprocess.TimeoutExpired:
        log.error("ffmpeg timed out after 300 s — killing process")
        _cleanup(tmp_video)
        return False
    except FileNotFoundError:
        log.error("ffmpeg not found — install it with: sudo apt install ffmpeg")
        _cleanup(tmp_video)
        return False
    except Exception as exc:  # noqa: BLE001
        log.error("Unexpected error in build_timelapse: %s", exc)
        _cleanup(tmp_video)
        return False
    finally:
        if tmp_list and os.path.exists(tmp_list):
            os.unlink(tmp_list)


def _display_size() -> str:
    """Return 'WxH' string from config, with an even-number safeguard for x264."""
    try:
        from config import DISPLAY_WIDTH, DISPLAY_HEIGHT  # type: ignore
        w = DISPLAY_WIDTH if DISPLAY_WIDTH % 2 == 0 else DISPLAY_WIDTH - 1
        h = DISPLAY_HEIGHT if DISPLAY_HEIGHT % 2 == 0 else DISPLAY_HEIGHT - 1
        return f"{w}:{h}"
    except ImportError:
        return "800:480"


def _cleanup(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# CLI entry point (for manual testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
    cli_log = logging.getLogger("timelapse-cli")

    parser = argparse.ArgumentParser(description="Build a timelapse from JPEG frames.")
    parser.add_argument("frames_dir", help="Directory containing .jpg frames")
    parser.add_argument("output_video", help="Output MP4 path")
    a = parser.parse_args()

    ok = build_timelapse(a.frames_dir, a.output_video, cli_log)
    sys.exit(0 if ok else 1)
