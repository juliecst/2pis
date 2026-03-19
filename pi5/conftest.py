"""
Ensure pi5/ is first on sys.path when tests are run from this directory.
The _pi5cfg helper module ensures pi5/config.py is always loaded correctly.
"""
import os
import sys

_PI5_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.path[:1] != [_PI5_DIR]:
    while _PI5_DIR in sys.path:
        sys.path.remove(_PI5_DIR)
    sys.path.insert(0, _PI5_DIR)
