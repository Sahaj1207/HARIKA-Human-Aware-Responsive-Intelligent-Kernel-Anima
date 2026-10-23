// Publishes a release built by release.mjs, so every installed HARIKA offers it.
//
// Usage (from frontend/):  node scripts/publish.mjs 0.2.2
//
// 1. Creates GitHub release v<version> on the update host with the installer, its
//    .sig and latest.json (the installer is downloaded from here).
// 2. Commits latest.json to the host's main branch, which is the fast address HARIKA
//    checks (raw.githubusercontent.com answers in well under a second; release
//    download links can take 20+ seconds to redirect).
// Needs the GitHub CLI (gh) signed in to the account that owns the host.
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOST = process.env.HARIKA_UPDATE_REPO ?? 'Sahaj1207/app-releases';
const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const [version] = process.argv.slice(2);
const folder = join(root, 'release', version ?? '');
const installer = `HARIKA_${version}_x64-setup.exe`;
const files = [installer, `${installer}.sig`, 'latest.json'].map((name) => join(folder, name));

if (!/^\d+\.\d+\.\d+$/.test(version ?? '') || !files.every(existsSync)) {
  console.error(`Build it first: node scripts/release.mjs ${version ?? '<version>'} "notes"`);
  process.exit(1);
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' });
  if (result.status !== 0) {
    console.error(`Failed: ${command} ${args.join(' ')}`);
    process.exit(result.status ?? 1);
  }
}

// 1. The release holding the update package.
run('gh', ['release', 'create', `v${version}`, '--repo', HOST, '--title', version, '--notes', `HARIKA ${version}`, ...files]);

// 2. The fast address HARIKA reads.
const checkout = mkdtempSync(join(tmpdir(), 'harika-publish-'));
try {
  run('gh', ['repo', 'clone', HOST, checkout, '--', '--depth', '1']);
  copyFileSync(join(folder, 'latest.json'), join(checkout, 'latest.json'));
  run('git', ['add', 'latest.json'], checkout);
  run('git', ['commit', '-m', `latest.json for ${version}`], checkout);
  run('git', ['push', 'origin', 'HEAD'], checkout);
} finally {
  rmSync(checkout, { recursive: true, force: true });
}
console.log(`\nPublished ${version}. Installed copies of HARIKA will offer it on their next check.`);
