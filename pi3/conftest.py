"""Ensure pi3/ is first on sys.path when tests are run from this directory."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
