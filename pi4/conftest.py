"""
Ensure pi4/ is first on sys.path when tests are run from this directory.
The _pi4cfg helper module ensures pi4/config.py is always loaded correctly.
"""
import os
import sys

_PI4_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.path[:1] != [_PI4_DIR]:
    while _PI4_DIR in sys.path:
        sys.path.remove(_PI4_DIR)
    sys.path.insert(0, _PI4_DIR)
