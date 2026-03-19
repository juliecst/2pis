"""
Root conftest.py
================
When pytest collects tests from both pi1/ and pi5/ in the same session the
two directories each contain a module named config.py.  The per-directory
conftest files handle this for runs from a single directory; this file handles
the combined case by using pytest_pycollect_makemodule to swap sys.path and
sys.modules right before each test file is imported.
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PI1  = os.path.join(_ROOT, "pi1")
_PI5  = os.path.join(_ROOT, "pi5")

_PI1_MODS = ("config", "camera")
_PI5_MODS = ("config", "timelapse", "server", "player")


def _load_dir_modules(primary: str, module_names: tuple) -> None:
    """Force-load named modules from *primary* directory into sys.modules."""
    for name in module_names:
        fpath = os.path.join(primary, f"{name}.py")
        if not os.path.exists(fpath):
            continue
        spec = importlib.util.spec_from_file_location(name, fpath)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass  # suppress import-time failures (missing hardware libs, etc.)


def _activate_dir(primary: str, other: str, module_names: tuple) -> None:
    """Put *primary* first on sys.path, evict *other*, reload modules."""
    while other in sys.path:
        sys.path.remove(other)
    if sys.path[:1] != [primary]:
        while primary in sys.path:
            sys.path.remove(primary)
        sys.path.insert(0, primary)
    for name in module_names:
        sys.modules.pop(name, None)
    _load_dir_modules(primary, module_names)


def pytest_pycollect_makemodule(module_path, parent):
    """Called just before a test module is imported — fix the path first."""
    fdir = str(module_path.parent.resolve())
    if fdir == _PI1:
        _activate_dir(_PI1, _PI5, _PI1_MODS)
    elif fdir == _PI5:
        _activate_dir(_PI5, _PI1, _PI5_MODS)
