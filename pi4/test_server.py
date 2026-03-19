#!/usr/bin/env python3
"""
Pi4 — Offline Tests
====================
Tests for the server, timelapse builder, and player logic.
No real hardware, network, or ffmpeg required.

Run:
    cd pi4
    python3 -m pytest test_server.py -v
  or
    python3 test_server.py
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PI4_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PI4_DIR)

# Import pi4 config via its unique module name (_pi4cfg) to avoid
# shadowing by pi3/config.py when both test suites run in the same session.
import _pi4cfg as config  # noqa: F401

# Also register pi4/config as the generic 'config' so server.py's
# `from config import (...)` always finds the pi4 version.
import importlib.util as _ilu

_pi4_conf_spec = _ilu.spec_from_file_location(
    "config", os.path.join(_PI4_DIR, "config.py")
)
_pi4_conf_mod = _ilu.module_from_spec(_pi4_conf_spec)
sys.modules["config"] = _pi4_conf_mod
_pi4_conf_spec.loader.exec_module(_pi4_conf_mod)

# Explicitly load server and timelapse from pi4/ so sys.modules entries used
# by patch("server.*") and patch("timelapse.*") always resolve to the pi4 versions.

def _load_pi4(name: str):
    spec = _ilu.spec_from_file_location(name, os.path.join(_PI4_DIR, f"{name}.py"))
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_server_mod    = _load_pi4("server")
_timelapse_mod = _load_pi4("timelapse")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiny_jpeg() -> bytes:
    """Return a minimal valid 1×1 JPEG for upload tests."""
    buf = io.BytesIO()
    try:
        from PIL import Image
        import numpy as np
        img = Image.fromarray(
            (
                __import__("numpy").zeros((1, 1, 3), dtype="uint8") + 128
            )
        )
        img.save(buf, format="JPEG")
    except ImportError:
        # hard-coded 1×1 grey JPEG
        buf.write(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7)\x01\x02\x02\x02"
            b"\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb"
            b"\xd4P\x00\x00\x00\x00\x1f\xff\xd9"
        )
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Flask app tests
# ---------------------------------------------------------------------------

class TestServerEndpoints(unittest.TestCase):
    """Test Flask routes with an in-memory test client."""

    def setUp(self):
        # Patch storage so tests never touch real filesystem or USB
        self.tmp = tempfile.mkdtemp()
        self.frames_dir = os.path.join(self.tmp, "frames")
        self.video_path = os.path.join(self.tmp, "timelapse.mp4")
        os.makedirs(self.frames_dir)

        # Patch config paths and build_timelapse to avoid ffmpeg dependency
        patcher_storage = patch(
            "server.get_storage_paths",
            return_value=(self.frames_dir, self.video_path),
        )
        patcher_build = patch("server.build_timelapse", return_value=True)
        patcher_usb = patch("server.is_usb_mounted", return_value=False)

        self.mock_storage = patcher_storage.start()
        self.mock_build   = patcher_build.start()
        self.mock_usb     = patcher_usb.start()
        self.addCleanup(patcher_storage.stop)
        self.addCleanup(patcher_build.stop)
        self.addCleanup(patcher_usb.stop)

        app = _server_mod.app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- /status ---

    def test_status_returns_200(self):
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)

    def test_status_json_fields(self):
        resp = self.client.get("/status")
        data = json.loads(resp.data)
        required_fields = {
            "status", "frame_count", "last_timestamp",
            "video_path", "video_exists", "usb_mounted",
        }
        self.assertTrue(required_fields.issubset(data.keys()))

    def test_status_frame_count_zero_initially(self):
        resp = self.client.get("/status")
        data = json.loads(resp.data)
        self.assertEqual(data["frame_count"], 0)

    # --- /receive_frame ---

    def test_receive_frame_success(self):
        jpeg = _make_tiny_jpeg()
        resp = self.client.post(
            "/receive_frame",
            data={
                "frame": (io.BytesIO(jpeg), "20240101_120000.jpg"),
                "timestamp": "20240101_120000",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")

    def test_receive_frame_saves_file(self):
        jpeg = _make_tiny_jpeg()
        self.client.post(
            "/receive_frame",
            data={
                "frame": (io.BytesIO(jpeg), "20240101_120001.jpg"),
                "timestamp": "20240101_120001",
            },
            content_type="multipart/form-data",
        )
        saved = os.listdir(self.frames_dir)
        self.assertIn("20240101_120001.jpg", saved)

    def test_receive_frame_missing_file_returns_400(self):
        resp = self.client.post(
            "/receive_frame",
            data={"timestamp": "20240101_120002"},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)

    def test_receive_frame_increments_count(self):
        jpeg = _make_tiny_jpeg()
        for i in range(3):
            ts = f"20240101_1200{i:02d}"
            self.client.post(
                "/receive_frame",
                data={
                    "frame": (io.BytesIO(jpeg), f"{ts}.jpg"),
                    "timestamp": ts,
                },
                content_type="multipart/form-data",
            )
        resp = self.client.get("/status")
        data = json.loads(resp.data)
        self.assertEqual(data["frame_count"], 3)

    # --- /frames ---

    def test_list_frames_empty(self):
        resp = self.client.get("/frames")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["count"], 0)

    def test_list_frames_after_upload(self):
        jpeg = _make_tiny_jpeg()
        ts = "20240101_120005"
        self.client.post(
            "/receive_frame",
            data={
                "frame": (io.BytesIO(jpeg), f"{ts}.jpg"),
                "timestamp": ts,
            },
            content_type="multipart/form-data",
        )
        resp = self.client.get("/frames")
        data = json.loads(resp.data)
        self.assertGreater(data["count"], 0)
        self.assertIn(f"{ts}.jpg", data["frames"])

    # --- /rebuild ---

    def test_rebuild_endpoint_returns_200(self):
        resp = self.client.get("/rebuild")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Timelapse builder tests
# ---------------------------------------------------------------------------

class TestTimelapseBuilder(unittest.TestCase):
    """Tests for timelapse.build_timelapse() — ffmpeg is mocked."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.frames_dir = os.path.join(self.tmp, "frames")
        os.makedirs(self.frames_dir)
        self.output = os.path.join(self.tmp, "out.mp4")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_jpeg(self, name: str):
        path = os.path.join(self.frames_dir, name)
        with open(path, "wb") as f:
            f.write(_make_tiny_jpeg())
        return path

    def test_build_returns_false_when_no_frames(self):
        build_timelapse = _timelapse_mod.build_timelapse
        ok = build_timelapse(self.frames_dir, self.output)
        self.assertFalse(ok)

    @patch("subprocess.run")
    def test_build_calls_ffmpeg(self, mock_run):
        """With frames present, build_timelapse should call ffmpeg."""
        mock_run.return_value = MagicMock(returncode=0)
        self._write_jpeg("frame1.jpg")
        # Create a fake output file so os.replace works
        tmp_video = self.output + config.TEMP_VIDEO_SUFFIX
        Path(tmp_video).write_bytes(b"fake mp4 content")

        build_timelapse = _timelapse_mod.build_timelapse
        ok = build_timelapse(self.frames_dir, self.output)
        self.assertTrue(ok)
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("ffmpeg", cmd_args)

    @patch("subprocess.run")
    def test_build_returns_false_on_ffmpeg_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr=b"some error")
        self._write_jpeg("frame1.jpg")

        build_timelapse = _timelapse_mod.build_timelapse
        ok = build_timelapse(self.frames_dir, self.output)
        self.assertFalse(ok)

    @patch("subprocess.run")
    def test_build_returns_false_when_ffmpeg_missing(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")
        self._write_jpeg("frame1.jpg")

        build_timelapse = _timelapse_mod.build_timelapse
        ok = build_timelapse(self.frames_dir, self.output)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Storage helper tests
# ---------------------------------------------------------------------------

class TestStorageHelpers(unittest.TestCase):
    """Test is_usb_mounted / get_storage_paths logic."""

    @patch("server.is_usb_mounted", return_value=True)
    def test_get_storage_paths_usb_when_mounted(self, _):
        get_storage_paths = _server_mod.get_storage_paths
        frames_dir, video_path = get_storage_paths()
        self.assertEqual(frames_dir, config.USB_FRAMES_DIR)
        self.assertEqual(video_path, config.USB_VIDEO_PATH)

    @patch("server.is_usb_mounted", return_value=False)
    def test_get_storage_paths_local_when_not_mounted(self, _):
        get_storage_paths = _server_mod.get_storage_paths
        frames_dir, video_path = get_storage_paths()
        self.assertEqual(frames_dir, config.LOCAL_FRAMES_DIR)
        self.assertEqual(video_path, config.LOCAL_VIDEO_PATH)


# ---------------------------------------------------------------------------
# Config sanity tests
# ---------------------------------------------------------------------------

class TestPi4Config(unittest.TestCase):
    def test_server_port_is_positive(self):
        self.assertGreater(config.SERVER_PORT, 0)

    def test_timelapse_fps_valid(self):
        self.assertGreater(config.TIMELAPSE_FPS, 0)
        self.assertLessEqual(config.TIMELAPSE_FPS, 120)

    def test_display_dimensions_even(self):
        # x264 requires even dimensions
        self.assertEqual(config.DISPLAY_WIDTH % 2, 0)
        self.assertEqual(config.DISPLAY_HEIGHT % 2, 0)

    def test_usb_and_local_paths_differ(self):
        self.assertNotEqual(config.USB_VIDEO_PATH, config.LOCAL_VIDEO_PATH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
