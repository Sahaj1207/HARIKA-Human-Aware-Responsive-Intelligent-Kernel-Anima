// Publishes a release built by release.mjs, so every installed HARIKA offers it.
//
// Usage (from frontend/):  node scripts/publish.mjs 0.2.10
//
// 1. Creates GitHub release v<version> on HARIKA's own repository, with the installer, its
//    .sig and latest.json, and the release notes (the installer is downloaded from here).
// 2. Commits updates/latest.json to this repository's main branch: the fast address HARIKA
//    checks (raw.githubusercontent.com answers in well under a second; release download
//    links can take 20+ seconds to redirect).
// 3. Hand-over: copies (0.2.9 and earlier) check Sahaj1207/app-releases, so its latest.json is
//    updated too, pointing at the same installer. Once they've updated, they check here.
// Needs the GitHub CLI (gh) signed in to the account that owns both repositories.
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOME = process.env.HARIKA_UPDATE_REPO ?? 'Sahaj1207/HARIKA-Human-Aware-Responsive-Intelligent-Kernel-Anima';
const OLD_HOST = process.env.HARIKA_OLD_UPDATE_REPO ?? 'Sahaj1207/app-releases'; // '' once nobody is on 0.2.9 or earlier
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

const latest = JSON.parse(readFileSync(join(folder, 'latest.json'), 'utf8'));
const notes = `${latest.notes || `HARIKA ${version}`}\n\n**Download:** ${installer} below (Windows). Installed copies of HARIKA offer this update by themselves.`;

// 1. The release, on HARIKA's own page.
run('gh', ['release', 'create', `v${version}`, '--repo', HOME, '--title', `HARIKA ${version}`, '--notes', notes, ...files]);

// 2. The fast address HARIKA reads, in this repository.
mkdirSync(join(root, 'updates'), { recursive: true });
copyFileSync(join(folder, 'latest.json'), join(root, 'updates', 'latest.json'));
run('git', ['add', 'updates/latest.json'], root);
run('git', ['commit', '-m', `Update address: HARIKA ${version}`, '--', 'updates/latest.json'], root);
run('git', ['push', 'origin', 'HEAD'], root);

// 3. The old address, for copies that still check it.
if (OLD_HOST) {
  const checkout = mkdtempSync(join(tmpdir(), 'harika-publish-'));
  try {
    run('gh', ['repo', 'clone', OLD_HOST, checkout, '--', '--depth', '1']);
    copyFileSync(join(folder, 'latest.json'), join(checkout, 'latest.json'));
    run('git', ['add', 'latest.json'], checkout);
    run('git', ['commit', '-m', `latest.json for ${version} (releases now live in ${HOME})`], checkout);
    run('git', ['push', 'origin', 'HEAD'], checkout);
  } finally {
    rmSync(checkout, { recursive: true, force: true });
  }
}
console.log(`\nPublished ${version}. Installed copies of HARIKA will offer it on their next check.`);
