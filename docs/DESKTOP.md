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

### Live answers, weather and your day

- Ask about anything current ("what's the latest F1 news?", "who won the
  match yesterday?"): HARIKA searches the web and news, reads the top pages,
  and answers in a few sentences with its sources. "Open the first one" opens a
  source.
- "How's the weather?", "will it rain in Mumbai tomorrow?": forecasts for the
  next 7 days from Open-Meteo.
- "Brief me": the weather, today's reminders and the top headlines. Turn on
  **Morning briefing** in **Settings > General > Your day** to get it once a day
  at a time you choose (shown, and spoken if voice is on).

Set **Home city** there too; otherwise "here" is the computer's approximate
location from its internet address (ipwho.is), which can be a nearby town.
With the local model, an answer takes about 20 to 40 seconds on a laptop CPU
because the model has to read the sources; a cloud model in Settings > Brain
answers in a few seconds. Web pages are treated as material to read, never as
instructions.

### Calendar and email (Google)

Ask "what's on my calendar tomorrow?", "add dentist on Friday at 5pm", "move
my dentist appointment to 6", "any new emails?", "read the first one", "reply
saying I'll be there" or "email Priya that I'll be late". The morning briefing
also includes today's events and new email.

- Adding an event happens straight away (only on your own calendar; nobody is
  invited) and HARIKA tells you if it overlaps something.
- Moving or deleting an event, and sending any email, always shows exactly
  what will happen and waits for your "yes". "Make it shorter" (or any change)
  redrafts an email; anything other than a yes cancels.
- Email text is written by other people, so HARIKA only summarizes it or
  replies to it; instructions inside an email are never followed.
- To find "Priya", HARIKA looks for her address in your past email. If it
  finds several, or none, it asks.

**For people using HARIKA:** open **Settings > Accounts** and press **Sign in
with Google**. Each person connects their own account; on a shared computer,
every Windows user has separate HARIKA settings and keychain.

**For the developer, once:** Google only lets registered apps read Gmail.
Register HARIKA, download its OAuth client JSON to `secrets/google-client.json`
(git-ignored), and `npm run desktop:build` builds it into the installer. Without
that file, people can add their own client under **Settings > Accounts >
Advanced**. The registration steps:

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project (any name, like HARIKA).
2. Under **APIs & Services > Library**, enable the **Google Calendar API** and
   the **Gmail API**.
3. Under **Google Auth Platform**, set up the app: audience **External**, name
   HARIKA, your email as support contact, and add the Gmail address that will
   sign in as a **test user**.
4. Under **Clients**, create a client of type **Desktop app** and download its
   JSON right away (save it as `secrets/google-client.json`, or paste the ID
   and secret under Advanced).
5. While the app is in **Testing**, only the test users listed under
   **Audience** can sign in, and Google signs them out every 7 days. To open it
   to anyone, complete **Branding** (home page and privacy policy links) and
   choose **Publish app**. Unverified, it works for up to 100 people, who see a
   "Google hasn't verified this app" warning once (**Advanced > Go to
   HARIKA**). More than that needs Google's verification; reading Gmail also
   needs Google's paid security assessment.

Then press **Sign in with Google** and allow calendar and Gmail access. HARIKA
asks for: your calendar's events, reading Gmail, and sending Gmail. The sign-in
returns to HARIKA on this computer (127.0.0.1). The client secret and Google's
refresh token are kept in Windows Credential Manager; **Disconnect** revokes
HARIKA's access at Google and removes them.

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
| Google client ID and account email | `%APPDATA%\com.harika.desktop\settings\google.json` |
| Google client secret and sign-in | Windows Credential Manager (service "HARIKA") |

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
