"""How long since the user last touched the keyboard or mouse (Windows: GetLastInputInfo)."""
import ctypes
import platform
from typing import Optional


def seconds_idle() -> Optional[float]:
    """None where the OS can't tell."""
    if platform.system() != "Windows":
        return None

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    # Both counters are milliseconds since boot; the subtraction wraps like the 32-bit tick count does.
    elapsed = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return elapsed / 1000.0
