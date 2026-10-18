// Builds a signed HARIKA release for in-app updates.
//
// Usage (from frontend/):  node scripts/release.mjs 0.2.0 "What's new, in a sentence or two"
//
// 1. Sets the version in tauri.conf.json, package.json and Cargo.toml.
// 2. Builds the installer, signing the update with secrets/updater.key.
// 3. Writes release/<version>/ (repo root): the installer, its .sig and latest.json,
//    which is what HARIKA checks for updates.
// Publishing those three files is a separate, deliberate step (see docs/DESKTOP.md).
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = join(dirname(fileURLToPath(import.meta.url)), '..');
const root = join(frontend, '..');
const [version, notes = ''] = process.argv.slice(2);
const downloadBase = process.env.HARIKA_RELEASE_BASE_URL
  ?? `https://github.com/Sahaj1207/harika-releases/releases/download/v${version}`;

if (!/^\d+\.\d+\.\d+$/.test(version ?? '')) {
  console.error('Give a version like 0.2.0');
  process.exit(1);
}
const keyFile = join(root, 'secrets', 'updater.key');
const passwordFile = join(root, 'secrets', 'updater-key.password');
if (!existsSync(keyFile) || !existsSync(passwordFile)) {
  console.error('secrets/updater.key and secrets/updater-key.password are needed to sign the update.');
  process.exit(1);
}

// 1. One version everywhere.
const confPath = join(frontend, 'src-tauri', 'tauri.conf.json');
const conf = JSON.parse(readFileSync(confPath, 'utf8'));
conf.version = version;
writeFileSync(confPath, JSON.stringify(conf, null, 2) + '\n');
const pkgPath = join(frontend, 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
pkg.version = version;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');
const cargoPath = join(frontend, 'src-tauri', 'Cargo.toml');
writeFileSync(cargoPath, readFileSync(cargoPath, 'utf8').replace(/^version = "[^"]+"/m, `version = "${version}"`));

// 2. Build and sign.
const env = {
  ...process.env,
  TAURI_SIGNING_PRIVATE_KEY: readFileSync(keyFile, 'utf8'),
  TAURI_SIGNING_PRIVATE_KEY_PASSWORD: readFileSync(passwordFile, 'utf8').trim(),
};
const build = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'desktop:build'],
  { cwd: frontend, env, stdio: 'inherit', shell: process.platform === 'win32' });
if (build.status !== 0) process.exit(build.status ?? 1);

// 3. The update package and the file HARIKA reads.
const bundle = join(frontend, 'src-tauri', 'target', 'release', 'bundle', 'nsis');
const installer = `HARIKA_${version}_x64-setup.exe`;
if (!existsSync(join(bundle, `${installer}.sig`))) {
  console.error(`No signature was produced for ${installer}; check createUpdaterArtifacts and the signing key.`);
  process.exit(1);
}
const out = join(root, 'release', version);
mkdirSync(out, { recursive: true });
copyFileSync(join(bundle, installer), join(out, installer));
copyFileSync(join(bundle, `${installer}.sig`), join(out, `${installer}.sig`));
const latest = {
  version,
  notes,
  pub_date: new Date().toISOString(),
  platforms: {
    'windows-x86_64': {
      signature: readFileSync(join(bundle, `${installer}.sig`), 'utf8').trim(),
      url: `${downloadBase}/${installer}`,
    },
  },
};
writeFileSync(join(out, 'latest.json'), JSON.stringify(latest, null, 2) + '\n');
console.log(`\nRelease ${version} is ready in release/${version}/ (installer, .sig, latest.json).`);
