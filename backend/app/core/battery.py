"""Battery level and charging state from the operating system (Windows: GetSystemPowerStatus)."""
import ctypes
import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class Battery:
    percent: int
    charging: bool       # plugged in
    minutes_left: Optional[int] = None


def battery_status() -> Optional[Battery]:
    """None on desktops without a battery, or where the OS can't tell."""
    if platform.system() != "Windows":
        return None

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

    status = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None
    if status.BatteryFlag & 128 or status.BatteryLifePercent > 100:  # 128: no system battery; 255: unknown
        return None
    seconds = status.BatteryLifeTime
    minutes = None if seconds in (0xFFFFFFFF, -1) else seconds // 60
    return Battery(percent=status.BatteryLifePercent, charging=status.ACLineStatus == 1, minutes_left=minutes)
