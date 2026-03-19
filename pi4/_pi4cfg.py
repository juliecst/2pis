"""
_pi4cfg — Pi4 config loader
============================
Loads pi4/config.py from the directory this file lives in, using importlib,
so it is always the correct config regardless of what is on sys.path or
cached in sys.modules['config'].

Import this instead of 'config' in test files to avoid collisions with pi5's
config.py when both test suites are collected in the same pytest session.
"""
import importlib.util
import os
import sys

_PI4_DIR = os.path.dirname(os.path.abspath(__file__))
_CONF_PATH = os.path.join(_PI4_DIR, "config.py")

_spec = importlib.util.spec_from_file_location("_pi4cfg", _CONF_PATH)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export every public name so callers can do  `from _pi4cfg import *`
# or `import _pi4cfg as config`.
SERVER_HOST       = _mod.SERVER_HOST
SERVER_PORT       = _mod.SERVER_PORT
USB_MOUNT_POINT   = _mod.USB_MOUNT_POINT
USB_FRAMES_DIR    = _mod.USB_FRAMES_DIR
USB_VIDEO_PATH    = _mod.USB_VIDEO_PATH
LOCAL_FRAMES_DIR  = _mod.LOCAL_FRAMES_DIR
LOCAL_VIDEO_PATH  = _mod.LOCAL_VIDEO_PATH
TEMP_VIDEO_SUFFIX = _mod.TEMP_VIDEO_SUFFIX
TIMELAPSE_FPS     = _mod.TIMELAPSE_FPS
REBUILD_EVERY_N   = _mod.REBUILD_EVERY_N
DISPLAY_WIDTH     = _mod.DISPLAY_WIDTH
DISPLAY_HEIGHT    = _mod.DISPLAY_HEIGHT
MPV_EXTRA_OPTS    = _mod.MPV_EXTRA_OPTS
LOG_FILE          = _mod.LOG_FILE
LOG_MAX_BYTES     = _mod.LOG_MAX_BYTES
LOG_BACKUP_COUNT  = _mod.LOG_BACKUP_COUNT

# Make sure pi4/ is on sys.path so other pi4 modules can be imported
if _PI4_DIR not in sys.path:
    sys.path.insert(0, _PI4_DIR)
