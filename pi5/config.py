"""
Pi5 Configuration
-----------------
Edit these values to match your setup.
"""

import os

# --- Server ---
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# --- Storage ---
# Primary storage on USB stick (recommended for persistence across power cycles)
USB_MOUNT_POINT = "/media/pi/TIMELAPSE"   # label your USB stick "TIMELAPSE"
USB_FRAMES_DIR  = os.path.join(USB_MOUNT_POINT, "frames")
USB_VIDEO_PATH  = os.path.join(USB_MOUNT_POINT, "timelapse.mp4")

# Local fallback (used when USB stick is not mounted)
LOCAL_FRAMES_DIR = os.path.expanduser("~/timelapse_frames")
LOCAL_VIDEO_PATH = os.path.expanduser("~/timelapse.mp4")

# Temporary video path used during rebuild to allow atomic rename
TEMP_VIDEO_SUFFIX = ".tmp.mp4"

# --- Timelapse ---
TIMELAPSE_FPS    = 24    # output video frames-per-second
REBUILD_EVERY_N  = 10    # rebuild video after every N new frames (0 = every frame)

# --- Display (Waveshare 5-inch) ---
DISPLAY_WIDTH  = 800
DISPLAY_HEIGHT = 480
# Extra mpv options; set "" if not needed
MPV_EXTRA_OPTS = "--no-osc --no-osd-bar"

# --- Logging ---
LOG_FILE = "/home/pi/pi5-server.log"
LOG_MAX_BYTES    = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
