const STATUS_TEXT = {
  connected: 'Connected to HARIKA',
  disconnected: 'Not connected',
  'needs code': 'Paste the pairing code to connect',
};

async function show() {
  const { status, code } = await chrome.storage.local.get(['status', 'code']);
  document.getElementById('status').textContent = STATUS_TEXT[status] || status || 'Not connected';
  document.getElementById('dot').classList.toggle('on', status === 'connected');
  if (code && !document.getElementById('code').value) document.getElementById('code').value = code;
}

document.getElementById('save').addEventListener('click', async () => {
  const code = document.getElementById('code').value.trim().toUpperCase();
  if (!code) return;
  await chrome.storage.local.set({ code, status: 'Connecting…' });
  show();
});

chrome.storage.onChanged.addListener(show);
show();
