#!/usr/bin/env python3
"""
Pi5 — Offline Tests
====================
Tests that run without a real camera or network connection.

Run:
    cd pi5
    python3 -m pytest test_capture.py -v
  or
    python3 test_capture.py
"""

import io
import sys
import os
import importlib.util
import unittest
from unittest.mock import MagicMock, patch

# Allow running from repo root or pi5/
_PI5_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PI5_DIR)

# Import pi5 config via its unique module name (_pi5cfg) to avoid
# shadowing by pi4/config.py when both test suites run in the same session.
import _pi5cfg as config

# Also register pi5/config as the generic 'config' so camera.py's
# `from config import (...)` always finds the pi5 version.
_pi5_conf_spec = importlib.util.spec_from_file_location(
    "config", os.path.join(_PI5_DIR, "config.py")
)
_pi5_conf_mod = importlib.util.module_from_spec(_pi5_conf_spec)
sys.modules["config"] = _pi5_conf_mod
_pi5_conf_spec.loader.exec_module(_pi5_conf_mod)

# Load camera from pi5/ explicitly so it picks up pi5/config
_camera_spec = importlib.util.spec_from_file_location(
    "camera", os.path.join(_PI5_DIR, "camera.py")
)
_camera_mod = importlib.util.module_from_spec(_camera_spec)
sys.modules["camera"] = _camera_mod   # needed for patch("camera.*") to work
_camera_spec.loader.exec_module(_camera_mod)

_generate_mock_frame  = _camera_mod._generate_mock_frame
capture_frame         = _camera_mod.capture_frame
send_frame            = _camera_mod.send_frame
check_pi4_reachable   = _camera_mod.check_pi4_reachable
PI4_URL               = _camera_mod.PI4_URL


class TestMockFrame(unittest.TestCase):
    """Tests for the mock frame generator (no camera required)."""

    def test_generate_mock_frame_returns_bytes(self):
        buf = io.BytesIO()
        _generate_mock_frame(buf)
        buf.seek(0)
        data = buf.read()
        self.assertGreater(len(data), 0)

    def test_generate_mock_frame_is_valid_jpeg(self):
        """JPEG files start with FF D8 and end with FF D9."""
        buf = io.BytesIO()
        _generate_mock_frame(buf)
        buf.seek(0)
        data = buf.read()
        self.assertEqual(data[:2], b"\xff\xd8", "Expected JPEG SOI marker")
        self.assertEqual(data[-2:], b"\xff\xd9", "Expected JPEG EOI marker")


class TestCaptureFrame(unittest.TestCase):
    """Tests for capture_frame() with mock camera."""

    def test_capture_with_mock_lib_returns_jpeg_bytes(self):
        """Passing lib='mock' should produce a non-empty JPEG."""
        data = capture_frame(camera=None, lib="mock")
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[:2], b"\xff\xd8")

    def test_capture_with_picamera2_calls_capture_array(self):
        """When lib='picamera2', we call camera.capture_array()."""
        import numpy as np
        from PIL import Image

        fake_array = np.zeros((480, 640, 3), dtype="uint8")
        mock_cam = MagicMock()
        mock_cam.capture_array.return_value = fake_array

        with patch("camera.JPEG_QUALITY", 85):
            data = capture_frame(mock_cam, "picamera2")

        mock_cam.capture_array.assert_called_once()
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

    def test_capture_with_picamera_uses_buf(self):
        """When lib='picamera', camera.capture() is called with a BytesIO."""

        def fake_capture(buf, format, quality):
            buf.write(b"\xff\xd8\xff\xd9")  # minimal valid JPEG

        mock_cam = MagicMock()
        mock_cam.capture.side_effect = fake_capture

        data = capture_frame(mock_cam, "picamera")
        mock_cam.capture.assert_called_once()
        self.assertEqual(data, b"\xff\xd8\xff\xd9")


class TestSendFrame(unittest.TestCase):
    """Tests for send_frame() — network calls are mocked."""

    def _make_frame(self) -> bytes:
        buf = io.BytesIO()
        _generate_mock_frame(buf)
        buf.seek(0)
        return buf.read()

    @patch("camera.requests.post")
    def test_send_frame_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        ok = send_frame(self._make_frame(), "20240101_120000")
        self.assertTrue(ok)
        mock_post.assert_called_once()

    @patch("camera.requests.post")
    def test_send_frame_retries_on_server_error(self, mock_post):
        """Server returns 500 every time → all retries exhausted → False."""
        mock_post.return_value = MagicMock(status_code=500)
        with patch("camera.RETRY_DELAY", 0):
            ok = send_frame(self._make_frame(), "20240101_120001")
        self.assertFalse(ok)
        self.assertEqual(mock_post.call_count, config.MAX_RETRIES)

    @patch("camera.requests.post")
    def test_send_frame_success_on_second_attempt(self, mock_post):
        """First call fails, second succeeds → True."""
        import requests as req
        mock_post.side_effect = [
            req.exceptions.ConnectionError("down"),
            MagicMock(status_code=200),
        ]
        with patch("camera.RETRY_DELAY", 0):
            ok = send_frame(self._make_frame(), "20240101_120002")
        self.assertTrue(ok)
        self.assertEqual(mock_post.call_count, 2)

    @patch("camera.requests.get")
    def test_check_pi4_reachable_returns_true_on_200(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        self.assertTrue(check_pi4_reachable())

    @patch("camera.requests.get")
    def test_check_pi4_reachable_returns_false_on_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError
        self.assertFalse(check_pi4_reachable())


class TestConfig(unittest.TestCase):
    """Sanity-check the configuration values."""

    def test_capture_interval_is_positive(self):
        self.assertGreater(config.CAPTURE_INTERVAL, 0)

    def test_resolution_is_valid(self):
        w, h = config.RESOLUTION
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_jpeg_quality_in_range(self):
        self.assertGreaterEqual(config.JPEG_QUALITY, 1)
        self.assertLessEqual(config.JPEG_QUALITY, 95)

    def test_max_retries_positive(self):
        self.assertGreater(config.MAX_RETRIES, 0)

    def test_pi4_host_is_set(self):
        self.assertIsInstance(config.PI4_HOST, str)
        self.assertTrue(len(config.PI4_HOST) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
