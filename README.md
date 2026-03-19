# 2pis — Museum Mold Timelapse

A simple, robust two-Raspberry-Pi setup for capturing and displaying a
continuous timelapse of mold growing, installed in a museum.

```
┌─────────────────────────────┐     HTTP POST     ┌──────────────────────────────────┐
│  Raspberry Pi 3             │ ───────────────►  │  Raspberry Pi 4                  │
│  HQ Camera + lens           │   (same WiFi)     │  Waveshare 5-inch display        │
│                             │                   │  USB stick (TIMELAPSE)           │
│  pi3/camera.py              │                   │  pi4/server.py  (Flask :5000)    │
│  → capture JPEG every 30 s  │                   │  pi4/timelapse.py (ffmpeg)       │
│  → send to Pi4              │                   │  pi4/player.py  (mpv loop)       │
└─────────────────────────────┘                   └──────────────────────────────────┘
```

- **No Samba, no shared filesystem** — Pi3 pushes frames to Pi4 over plain HTTP.
- **Persistent** — frames are stored on the USB stick; everything resumes
  automatically after a power cycle.
- **Self-healing** — all services restart automatically if they crash.

---

## Hardware

| Part | Details |
|------|---------|
| Raspberry Pi 3 | Camera node |
| Raspberry Pi HQ Camera | With lens, connected to Pi3 CSI port |
| Raspberry Pi 4 | Display / server node |
| Waveshare 5-inch display | 800 × 480, connected to Pi4 HDMI0 |
| USB stick | FAT32 or exFAT, **labelled `TIMELAPSE`** |
| WiFi router | Both Pis on the same network (GL-net Mango — SSID: **Goodlife**) |

---

## Project layout

```
2pis/
├── pi3/
│   ├── config.py         ← Pi3 settings (IP, interval, resolution)
│   ├── camera.py         ← Capture + send loop
│   └── test_capture.py   ← Offline tests (no camera needed)
├── pi4/
│   ├── config.py         ← Pi4 settings (paths, FPS, display)
│   ├── server.py         ← Flask HTTP server, receives frames
│   ├── timelapse.py      ← Build MP4 with ffmpeg
│   ├── player.py         ← Loop video on display with mpv
│   └── test_server.py    ← Offline tests (no hardware needed)
├── systemd/
│   ├── pi3-camera.service
│   ├── pi4-server.service
│   └── pi4-player.service
├── scripts/
│   ├── setup_pi3.sh      ← One-time setup on Pi3
│   ├── setup_pi4.sh      ← One-time setup on Pi4
│   ├── setup_network.sh  ← Configure museum WiFi + static IP
│   ├── check_status.sh   ← Live health check from any machine
│   ├── switch_wifi.sh    ← Change WiFi network
│   └── mount_usb.sh      ← Manually mount the USB stick
└── README.md
```

---

## Museum network

The museum uses a **GL-net Mango** travel router:

| Setting | Value |
|---------|-------|
| SSID | `Goodlife` |
| Password | `Goodlife` |
| Gateway | `192.168.8.1` |

### Static IP assignments

| Device | Hostname | Static IP |
|--------|----------|-----------|
| Raspberry Pi 3 (camera) | `pi3` | `192.168.8.10` |
| Raspberry Pi 4 (display) | `pi4` | `192.168.8.11` |

The setup scripts (`setup_pi3.sh` / `setup_pi4.sh`) configure WiFi and static
IPs automatically via `scripts/setup_network.sh`.  To reconfigure manually:

```bash
sudo bash /home/pi/2pis/scripts/setup_network.sh
```

To skip network configuration during setup (e.g. on a home network):

```bash
SKIP_NETWORK=1 bash scripts/setup_pi3.sh   # or setup_pi4.sh
```

---

## Initial setup

### 0 · Flash Pi OS

Flash **Raspberry Pi OS Lite (64-bit)** on both Pis using Raspberry Pi Imager.  
In the imager advanced options:
- Set hostname **`pi3`** on Pi3, **`pi4`** on Pi4.
- Enable SSH.
- Pre-configure your museum WiFi credentials.
- Set username `pi` and a password.

### 1 · Clone this repository on both Pis

```bash
# on each Pi
git clone <your-repo-url> /home/pi/2pis
```

### 2 · Prepare the USB stick

Format a USB stick as **FAT32** or **exFAT** and label it exactly **`TIMELAPSE`**
(case-sensitive).  Plug it into the Pi4.

### 3 · Set up Pi4 (display / server)

```bash
ssh pi@pi4.local
cd /home/pi/2pis
bash scripts/setup_pi4.sh
```

This installs Flask, ffmpeg, mpv, avahi-daemon, configures the udev auto-mount
rule, installs and enables the systemd services, and runs the offline tests.

### 4 · Edit Pi4 config (optional)

```bash
nano /home/pi/2pis/pi4/config.py
```

Key settings:
| Setting | Default | Meaning |
|---------|---------|---------|
| `USB_LABEL` (in setup script) | `TIMELAPSE` | USB stick label |
| `TIMELAPSE_FPS` | `24` | Playback speed of the video |
| `REBUILD_EVERY_N` | `10` | Rebuild video every N new frames |
| `DISPLAY_WIDTH/HEIGHT` | `800 × 480` | Waveshare 5-inch resolution |

### 5 · Set up Pi3 (camera)

The default `pi3/config.py` already points at Pi4's static IP on the museum
network (`192.168.8.11`).  If you use a different network, edit it first:

```python
PI4_HOST = "192.168.8.11"  # Pi4 static IP on the Goodlife network
CAPTURE_INTERVAL = 30      # seconds between frames
```

Then run the setup:

```bash
ssh pi@pi3.local
cd /home/pi/2pis
bash scripts/setup_pi3.sh
```

### 6 · Reboot both Pis

```bash
sudo reboot   # on Pi3
sudo reboot   # on Pi4
```

After reboot:
- Pi3 starts capturing and sending frames automatically.
- Pi4 receives frames, stores them on the USB stick, rebuilds the timelapse,
  and plays it on the display — all automatically.

---

## Display setup (Waveshare 5-inch)

Add to `/boot/config.txt` on Pi4:

```
# Waveshare 5-inch HDMI display
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=1
```

Reboot Pi4 after making this change.

---

## Waveshare display rotation

If the image appears rotated, add to `/boot/config.txt`:

```
display_rotate=2   # 0=normal, 1=90°, 2=180°, 3=270°
```

---

## After a power cut / daily shutdown

When the Pis are powered off and back on:

1. Pi4 boots, the USB stick is auto-mounted.
2. `pi4-server` starts and detects existing JPEG frames on the USB stick.
3. If no MP4 exists yet it rebuilds the timelapse from stored frames.
4. `pi4-player` starts and plays the timelapse on loop.
5. Pi3 boots and resumes capturing frames — new frames are appended to the
   existing set, and the timelapse is rebuilt periodically.

No manual intervention is needed.

---

## Debugging

### Check live status (from any machine on the same network)

```bash
bash scripts/check_status.sh              # uses 192.168.8.11 by default
bash scripts/check_status.sh 192.168.8.11 # or specify explicitly
```

Output:
```
=========================================
 2pis Status Check
 Pi4 address: 192.168.8.11:5000
=========================================

[Network]
  ✓ Pi4 is reachable on the network

[Pi4 Server]
  ✓ Server is up
  Frame count     : 142
  Last frame      : 20240315_143022
  Video exists    : True
  Video size      : 12.5 MB
  USB mounted     : True
  Rebuild running : False
  Pending rebuild : 3 frames
```

### Pi4 HTTP debug endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | JSON: frame count, video info, USB status |
| `/frames` | GET | JSON: list of all stored frame filenames |
| `/rebuild` | GET | Trigger an immediate timelapse rebuild |
| `/receive_frame` | POST | Receive a JPEG frame from Pi3 |

Example:

```bash
curl http://192.168.8.11:5000/status
curl http://192.168.8.11:5000/frames
curl http://192.168.8.11:5000/rebuild
```

### View service logs

```bash
# On Pi3
sudo journalctl -u pi3-camera -f

# On Pi4
sudo journalctl -u pi4-server -f
sudo journalctl -u pi4-player -f
```

### Manually test Pi3 camera

```bash
# Capture one frame and check the camera is working (no network needed)
cd /home/pi/2pis/pi3
python3 camera.py --dry-run

# Capture one frame and send it to Pi4 (requires Pi4 to be running)
python3 camera.py --test
```

### Manually test Pi4 player (desktop mode)

```bash
cd /home/pi/2pis/pi4
python3 player.py --debug    # no fullscreen, verbose output
```

### Manually trigger a timelapse rebuild

```bash
cd /home/pi/2pis/pi4
python3 timelapse.py /media/pi/TIMELAPSE/frames /media/pi/TIMELAPSE/timelapse.mp4
```

### Run offline unit tests

```bash
# Pi3 tests (no camera or network needed)
cd /home/pi/2pis/pi3
python3 -m pytest test_capture.py -v

# Pi4 tests (no hardware needed)
cd /home/pi/2pis/pi4
python3 -m pytest test_server.py -v
```

### Check USB stick

```bash
# On Pi4
bash /home/pi/2pis/scripts/mount_usb.sh
df -h /media/pi/TIMELAPSE
ls /media/pi/TIMELAPSE/frames | wc -l   # number of stored frames
```

### Service control

```bash
# Restart a service
sudo systemctl restart pi3-camera   # on Pi3
sudo systemctl restart pi4-server   # on Pi4
sudo systemctl restart pi4-player   # on Pi4

# Disable autostart temporarily
sudo systemctl disable pi3-camera

# Re-enable
sudo systemctl enable pi3-camera
```

---

## Switching WiFi network

The Pis ship configured for the museum WiFi (`Goodlife`).  If you need to
connect to a different network temporarily (e.g. your office for maintenance):

```bash
bash /home/pi/2pis/scripts/switch_wifi.sh "NewSSID" "NewPassword"
```

Or interactively:

```bash
bash /home/pi/2pis/scripts/switch_wifi.sh
# → prompts for SSID and password
```

To switch back to the museum network:

```bash
sudo bash /home/pi/2pis/scripts/setup_network.sh
```

Works with both NetworkManager (Pi OS Bookworm) and wpa_supplicant (Buster /
Bullseye).  The old config is backed up automatically.

---

## Network: using a static IP instead of `pi4.local`

Static IPs are pre-configured by `scripts/setup_network.sh` (see
[Museum network](#museum-network) above).  Pi3 `config.py` already points at
Pi4's static IP (`192.168.8.11`).

If you need **different** static IPs on another router, edit
`scripts/setup_network.sh` and `pi3/config.py`, then re-run the setup.

For a quick manual override **on Pi4** — add to `/etc/dhcpcd.conf`:

```
interface wlan0
static ip_address=192.168.8.11/24
static routers=192.168.8.1
static domain_name_servers=8.8.8.8
```

Then edit **Pi3** `config.py`:

```python
PI4_HOST = "192.168.8.11"
```

Restart services after making this change.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Pi3 log shows "Cannot reach Pi4" | Pi4 not running or wrong host | Check Pi4 services; verify `PI4_HOST` in `pi3/config.py` |
| Display shows nothing | Player waiting for first video | Wait a few minutes; check `sudo journalctl -u pi4-player -f` |
| USB stick not mounted | Wrong label or not plugged in | Label stick `TIMELAPSE`; run `bash scripts/mount_usb.sh` |
| Video stutters | USB stick is slow | Use a quality USB 3.0 stick or local storage |
| `ffmpeg not found` on Pi4 | Not installed | `sudo apt install ffmpeg` |
| `mpv not found` on Pi4 | Not installed | `sudo apt install mpv` |
| Camera not detected on Pi3 | Interface not enabled | `sudo raspi-config` → Interface Options → Camera |
| `pi4.local` not found | avahi not running or mDNS unavailable | Use static IP `192.168.8.11` instead; `sudo systemctl start avahi-daemon` on Pi4 |

