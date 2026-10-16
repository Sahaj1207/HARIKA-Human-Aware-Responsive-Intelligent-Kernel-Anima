# HARIKA desktop app

HARIKA ships as a desktop app (Tauri) that bundles the React interface and a
standalone build of the Python backend, so the person installing it needs no
Python or Node.

## Install (Windows)

1. Run `HARIKA_0.1.0_x64-setup.exe`. It installs for the current user only, with
   no administrator prompt, and adds HARIKA to the Start menu.
2. Windows may show "Windows protected your PC" because the installer isn't
   code-signed yet: choose **More info**, then **Run anyway**.
3. On first launch, HARIKA asks for your name and how it should think:
   - **On this computer**: install the free [Ollama](https://ollama.com/download)
     app, then let HARIKA download a model sized for the computer
     (about 2.5 GB, or 1 GB on machines with less than 8 GB of memory).
   - **With a cloud service**: sign in with OpenRouter, or paste a key from
     OpenAI, Anthropic, Google Gemini or Groq. Keys are stored in Windows
     Credential Manager.

Once running, HARIKA lives in the system tray. Press **Ctrl + Shift + Space**
anywhere to ask it something. Closing the window keeps it in the tray; use
**Quit HARIKA** in the tray menu to exit.

### Help in other apps ("continue this chat")

Open a chat (WhatsApp, Instagram or any web chat, Telegram, Teams...), then
ask HARIKA from the orb or its window:

- "continue this chat", "reply that I'll be late": HARIKA reads the visible
  conversation and shows a draft. Say "send it" to send, "make it shorter"
  (or any change) to redraft, or "no" to cancel. Nothing is sent without
  that explicit yes.
- "what's on my screen?", "summarize this": answers about the app you were
  just using.

HARIKA reads apps through Windows UI Automation (the accessibility interface
screen readers use), so it needs no screenshots. The visible text goes to the
conversation model chosen in Settings > Brain. Apps that hide their text from
accessibility tools can't be read yet.

### Voice ("Hey HARIKA")

Open **Settings > Voice** and download HARIKA's voice once (about 180 MB:
speech detection, speech recognition and one speaking voice). Then:

- Turn on **Listen for "Hey HARIKA"** and say "Hey HARIKA, open Spotify" (or
  "Hey HARIKA", wait for the chime, then speak). The orb appears, shows what
  it heard, answers and hides again.
- Or tap the microphone in the orb or the main window (push to talk).
- **Speak replies**: when you talk (default), always, or never. Eight voices
  (American and British), each downloaded when chosen.

Everything runs offline on the CPU (sherpa-onnx: Silero VAD, Moonshine speech
recognition, Piper voices). With listening on, speech near the microphone is
transcribed in memory and discarded unless it starts with "Hey HARIKA";
nothing is recorded. Windows must allow desktop apps to use the microphone
(Settings > Privacy & security > Microphone).

### Where things are stored

| What | Where |
|---|---|
| App | `%LOCALAPPDATA%\HARIKA` |
| Memories, reminders, settings | `%APPDATA%\com.harika.desktop` |
| Logs | `%LOCALAPPDATA%\com.harika.desktop\logs` |
| API keys | Windows Credential Manager (service "HARIKA") |
| Voice models | `%APPDATA%\com.harika.desktop\models` |

Uninstall from **Settings > Apps** like any other app.

## Build the installer

Prerequisites: Node 20+, Rust (stable) with the MSVC build tools, and
`backend/.venv` containing `backend/requirements.txt` plus `pyinstaller`.

```bash
cd frontend
npm install
npm run desktop:build
```

This runs two steps:

1. `npm run backend:bundle` freezes the backend with PyInstaller into
   `backend/build/dist/harika-backend/`.
2. `tauri build` builds the interface, compiles the shell in release mode and
   packages both into
   `frontend/src-tauri/target/release/bundle/nsis/HARIKA_<version>_x64-setup.exe`.

The installed app runs its backend on port **47801** (development uses 8000)
and passes the per-user data folder to it in `HARIKA_DATA_DIR`.

## Develop

```bash
cd frontend
npm run desktop
```

This starts Vite and the desktop shell; the shell starts the backend from
`backend/.venv` (or reuses one already running on port 8000).

## Not done yet

- **macOS**: the code supports it, but the `.dmg` must be built on a Mac
  (`npm run desktop:build`), and the orb window needs `macOSPrivateApi` for
  transparency. Brightness and media keys are Windows-only for now.
- **Code signing**: unsigned installers trigger SmartScreen on Windows and
  Gatekeeper on macOS. Signing needs a certificate (Windows) or an Apple
  Developer account (macOS).
- **Automatic updates**: not set up; install a newer setup file over the old one.
- **Ollama** is a separate install; HARIKA guides the user to it on first run.
