import os
import platform
from qpc_args import args
from enum import Enum


_win32_legacy_con = False
_win32_handle = None


if os.name == "nt":
    if platform.release().startswith("10"):
        # hack to enter virtual terminal mode,
        # could do it properly, but that's a lot of lines and this works just fine
        import subprocess
        subprocess.call('', shell=True)
    else:
        import ctypes
        _win32_handle = ctypes.windll.kernel32.GetStdHandle(-11)
        _win32_legacy_con = True


class Color(Enum):
    if _win32_legacy_con:
        RED = "4"
        DGREEN = "2"
        GREEN = "10"
        YELLOW = "6"
        BLUE = "1"
        MAGENTA = "13"
        CYAN = "3"  # or 9
    
        DEFAULT = "7"
    else:  # ansi escape chars
        RED = "\033[0;31m"
        DGREEN = "\033[0;32m"
        GREEN = "\033[1;32m"
        YELLOW = "\033[0;33m"
        BLUE = "\033[0;34m"
        MAGENTA = "\033[1;35m"
        CYAN = "\033[0;36m"
        
        DEFAULT = "\033[0m"


class Severity(Enum):
    WARNING = Color.YELLOW
    ERROR = Color.RED
    
    
WARNING_COUNT = 0


def warning(*text):
    if not args.hide_warnings:
        _print_severity(Severity.WARNING, "\n          ", *text)
    global WARNING_COUNT
    WARNING_COUNT += 1


def error(*text):
    _print_severity(Severity.ERROR, "\n        ", *text)
    quit(1)


def verbose(*text):
    if args.verbose:
        print("".join(text))


def verbose_color(color: Color, *text):
    if args.verbose:
        print_color(color, "".join(text))


def _print_severity(level: Severity, spacing: str, *text):
    print_color(level.value, f"[{level.name}] {spacing.join(text)}\n")
        
        
def win32_set_fore_color(color: int):
    if not ctypes.windll.kernel32.SetConsoleTextAttribute(_win32_handle, color):
        print(f"[ERROR] WIN32 Changing Colors Failed, Error Code: {str(ctypes.GetLastError())},"
              f" color: {color}, handle: {str(_win32_handle)}")
    
    
def print_color(color: Color, *text):
    if _win32_legacy_con:
        win32_set_fore_color(int(color.value))
        print("".join(text))
        win32_set_fore_color(int(Color.DEFAULT.value))
    else:
        print(color.value + "".join(text) + Color.DEFAULT.value)
