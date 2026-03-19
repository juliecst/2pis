"""
_pi1cfg — Pi1 config loader
============================
Loads pi1/config.py from the directory this file lives in, using importlib,
so it is always the correct config regardless of what is on sys.path or
cached in sys.modules['config'].

Import this instead of 'config' in test files to avoid collisions with pi5's
config.py when both test suites are collected in the same pytest session.
"""
import importlib.util
import os
import sys

_PI1_DIR  = os.path.dirname(os.path.abspath(__file__))
_CONF_PATH = os.path.join(_PI1_DIR, "config.py")

_spec = importlib.util.spec_from_file_location("_pi1cfg", _CONF_PATH)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export every public name
PI5_HOST             = _mod.PI5_HOST
PI5_PORT             = _mod.PI5_PORT
PI5_RECEIVE_ENDPOINT = _mod.PI5_RECEIVE_ENDPOINT
PI5_STATUS_ENDPOINT  = _mod.PI5_STATUS_ENDPOINT
CAPTURE_INTERVAL     = _mod.CAPTURE_INTERVAL
RESOLUTION           = _mod.RESOLUTION
JPEG_QUALITY         = _mod.JPEG_QUALITY
MAX_RETRIES          = _mod.MAX_RETRIES
RETRY_DELAY          = _mod.RETRY_DELAY
REQUEST_TIMEOUT      = _mod.REQUEST_TIMEOUT
LOG_FILE             = _mod.LOG_FILE
LOG_MAX_BYTES        = _mod.LOG_MAX_BYTES
LOG_BACKUP_COUNT     = _mod.LOG_BACKUP_COUNT

# Make sure pi1/ is on sys.path so other pi1 modules can be imported
if _PI1_DIR not in sys.path:
    sys.path.insert(0, _PI1_DIR)
