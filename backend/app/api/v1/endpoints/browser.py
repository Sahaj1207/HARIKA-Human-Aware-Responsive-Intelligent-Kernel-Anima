"""Website tasks' browser: HARIKA's extension connects here, and Settings shows its pairing code."""
import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, WebSocket

from app.core.paths import data_path
from app.tools.web.browser.extension_bridge import extension_bridge, new_pairing_code, pairing_code

router = APIRouter()


@router.websocket("/bridge")
async def extension_connection(websocket: WebSocket):
    await extension_bridge.serve(websocket)


def _status() -> dict:
    return {"connected": extension_bridge.connected(), "browser": extension_bridge.browser, "code": pairing_code()}


@router.get("/extension")
async def extension_status():
    return _status()


@router.post("/extension/new-code")
async def change_pairing_code():
    """A new pairing code; the extension using the old one is signed out."""
    new_pairing_code()
    return _status()


def extension_source() -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "browser-extension"
    return bundled if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[5] / "browser-extension"


def prepare_extension_folder() -> Path:
    """A copy of the extension (with page.js) in HARIKA's data folder, where the browser loads it from."""
    target = data_path("browser-extension")
    shutil.copytree(extension_source(), target, dirs_exist_ok=True)
    shutil.copy2(Path(__file__).resolve().parents[3] / "tools" / "web" / "browser" / "page.js", target / "page.js")
    return target


@router.post("/extension/open-folder")
async def open_extension_folder():
    """Shows the extension's folder, for the browser's "Load unpacked" button."""
    import os
    import subprocess
    folder = prepare_extension_folder()
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 (opens Explorer on HARIKA's own folder)
    else:
        subprocess.Popen(["open", str(folder)])
    return {**_status(), "folder": str(folder)}
