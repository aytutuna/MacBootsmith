import os
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def source_root():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def app_dir():
    if is_frozen():
        return os.path.dirname(os.path.realpath(sys.executable))
    return source_root()


def bundle_dir():
    if is_frozen():
        return getattr(sys, "_MEIPASS", None) or app_dir()
    return source_root()


def tools_dir():
    path = os.path.join(app_dir(), "Scripts")
    if is_frozen() and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


def data_dir():
    return os.path.join(bundle_dir(), "Scripts")
