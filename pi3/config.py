"""
Pi3 Configuration
-----------------
Edit these values to match your setup.
"""

# --- Network ---
# Pi4 address: static IP on the museum Goodlife network (GL-net Mango router)
PI4_HOST = "192.168.8.11"
PI4_PORT = 5000
PI4_RECEIVE_ENDPOINT = "/receive_frame"
PI4_STATUS_ENDPOINT   = "/status"

# --- Capture ---
CAPTURE_INTERVAL = 30   # seconds between frames (reduce for faster timelapse)
RESOLUTION       = (1920, 1080)  # (width, height); HQ cam max = (4056, 3040)
JPEG_QUALITY     = 85           # 1-95; higher = better quality, larger file

# --- Reliability ---
MAX_RETRIES  = 5    # retry a failed send this many times
RETRY_DELAY  = 10   # seconds between retries
REQUEST_TIMEOUT = 15  # seconds before a send attempt times out

# --- Logging ---
LOG_FILE = "/home/pi/pi3-camera.log"
LOG_MAX_BYTES  = 5 * 1024 * 1024   # 5 MB
LOG_BACKUP_COUNT = 3
