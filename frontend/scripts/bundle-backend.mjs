// Builds HARIKA's Python backend into a standalone folder (backend/build/dist/harika-backend)
// that the desktop installer ships, so users don't need Python installed.
// Usage: npm run backend:bundle   (requires backend/.venv with requirements + pyinstaller)
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { delimiter, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const backend = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'backend');
const python = process.platform === 'win32'
  ? join(backend, '.venv', 'Scripts', 'python.exe')
  : join(backend, '.venv', 'bin', 'python');

if (!existsSync(python)) {
  console.error(`No virtualenv at ${python}. Create it and install backend/requirements.txt and pyinstaller first.`);
  process.exit(1);
}

const args = [
  '-m', 'PyInstaller', 'harika_server.py',
  '--name', 'harika-backend',
  '--onedir', '--noconfirm', '--clean', '--console',
  '--distpath', 'build/dist', '--workpath', 'build/work', '--specpath', 'build',
  // Modules imported lazily inside functions and plugin-style packages.
  '--collect-submodules', 'app',
  '--collect-submodules', 'uvicorn',
  '--collect-submodules', 'keyring',
  ...(process.platform === 'win32' ? ['--collect-all', 'pycaw', '--collect-submodules', 'comtypes', '--collect-all', 'uiautomation'] : []),
  // Offline voice: native speech libraries and the PortAudio audio driver.
  '--collect-all', 'sherpa_onnx',
  '--collect-all', 'sounddevice',
  // Matching requests to abilities by meaning (the small model itself downloads on first start).
  '--collect-all', 'onnxruntime',
  '--collect-all', 'tokenizers',
  // Reading PDFs (its decoders are imported on demand).
  '--collect-all', 'pypdf',
  // Reading notifications (Windows' own API, through the WinRT bindings).
  '--collect-all', 'winrt',
];

// HARIKA's Google sign-in client (downloaded from Google Cloud Console, never committed).
// When present it's built in, so people only need to press "Sign in with Google".
const googleClient = join(backend, '..', 'secrets', 'google-client.json');
if (existsSync(googleClient)) {
  args.push('--add-data', `${googleClient}${delimiter}.`);
  console.log('Including the Google sign-in client from secrets/google-client.json');
} else {
  console.log('No secrets/google-client.json: people will need their own Google client (Settings > Accounts > Advanced).');
}

// HARIKA's Spotify app (its Client ID, {"client_id": "..."}), optional in the same way.
const spotifyClient = join(backend, '..', 'secrets', 'spotify-client.json');
if (existsSync(spotifyClient)) {
  args.push('--add-data', `${spotifyClient}${delimiter}.`);
  console.log('Including the Spotify Client ID from secrets/spotify-client.json');
}

const result = spawnSync(python, args, { cwd: backend, stdio: 'inherit' });
process.exit(result.status ?? 1);
