// HARIKA's browser extension. It connects to HARIKA on this computer and does website tasks in
// ONE tab it opened itself (grouped and labelled "HARIKA"). It never reads or touches your other
// tabs, and it acts only on HARIKA's instructions, which HARIKA checks first.
const PORTS = [47801, 8000]; // the installed HARIKA, then a development copy
let socket = null;

// ----------------------------------------------------------------- connecting to HARIKA

async function setStatus(status) {
  await chrome.storage.local.set({ status });
}

function browserName() {
  const brands = navigator.userAgentData?.brands?.map((b) => b.brand) || [];
  return brands.find((b) => /Edge|Chrome|Brave|Opera/.test(b) && !/Not|Chromium/.test(b)) || 'Chromium browser';
}

function connectTo(port, code) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/v1/browser/bridge`);
    let welcomed = false;
    ws.onopen = () => ws.send(JSON.stringify({ code, browser: browserName() }));
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'welcome') {
        welcomed = true;
        socket = ws;
        setStatus('connected');
        resolve();
      } else if (message.type === 'rejected') {
        setStatus(message.reason || 'HARIKA refused the connection');
        reject(new Error('rejected'));
      } else if (message.id) {
        handle(ws, message);
      }
    };
    ws.onerror = () => { if (!welcomed) reject(new Error('unreachable')); };
    ws.onclose = () => {
      if (socket === ws) {
        socket = null;
        setStatus('disconnected');
      }
      if (!welcomed) reject(new Error('closed'));
    };
  });
}

async function connect() {
  if (socket && socket.readyState <= 1) return;
  const { code } = await chrome.storage.local.get('code');
  if (!code) {
    await setStatus('needs code');
    return;
  }
  for (const port of PORTS) {
    try {
      await connectTo(port, code);
      return;
    } catch (error) {
      if (error.message === 'rejected') return;
    }
  }
  await setStatus("HARIKA isn't running");
}

// Keeps the connection (and this worker) alive, and reconnects when HARIKA restarts.
setInterval(() => { if (socket && socket.readyState === 1) socket.send('{"type":"ping"}'); }, 20000);
chrome.alarms.create('reconnect', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(connect);
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.storage.onChanged.addListener((changes) => {
  if (changes.code) {
    socket?.close();
    socket = null;
    connect();
  }
});
connect();

// ----------------------------------------------------------------- HARIKA's tab

async function harikaTab() {
  const { tab } = await chrome.storage.session.get('tab');
  if (tab != null) {
    try {
      await chrome.tabs.get(tab);
      return tab;
    } catch {
      // closed by the user: open a new one
    }
  }
  const window = await chrome.windows.getLastFocused({ windowTypes: ['normal'] }).catch(() => null);
  const created = await chrome.tabs.create({ url: 'about:blank', active: true, ...(window ? { windowId: window.id } : {}) });
  await chrome.storage.session.set({ tab: created.id });
  try {
    const group = await chrome.tabs.group({ tabIds: created.id });
    await chrome.tabGroups.update(group, { title: 'HARIKA', color: 'purple' });
  } catch {
    // tab groups unavailable: the tab still works
  }
  return created.id;
}

// A link HARIKA clicked opened a new tab: carry on there.
chrome.tabs.onCreated.addListener(async (tab) => {
  const { tab: current } = await chrome.storage.session.get('tab');
  if (current != null && tab.openerTabId === current) {
    await chrome.storage.session.set({ tab: tab.id });
    try {
      const { groupId } = await chrome.tabs.get(current);
      if (groupId >= 0) await chrome.tabs.group({ tabIds: tab.id, groupId });
    } catch {
      // not grouped
    }
  }
});

async function settle(tabId, seconds = 10) {
  const deadline = Date.now() + seconds * 1000;
  await new Promise((r) => setTimeout(r, 400));
  while (Date.now() < deadline) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === 'complete') break;
    await new Promise((r) => setTimeout(r, 300));
  }
  await new Promise((r) => setTimeout(r, 800));
}

async function onPage(tabId, name, params) {
  await chrome.scripting.executeScript({ target: { tabId }, files: ['page.js'] });
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId },
    func: (call, args) => {
      try {
        return { ok: true, value: window.__harika[call](...args) };
      } catch (error) {
        return { ok: false, error: error.message };
      }
    },
    args: [name, params],
  });
  const outcome = injection?.result;
  if (!outcome?.ok) throw new Error(outcome?.error || "HARIKA can't work on this page");
  return outcome.value;
}

// ----------------------------------------------------------------- what HARIKA can ask for

const COMMANDS = {
  async start() {
    await harikaTab();
    return true;
  },
  async open({ url }) {
    if (!/^https?:\/\//.test(url) && url !== 'about:blank') throw new Error('Only web addresses can be opened');
    const tabId = await harikaTab();
    await chrome.tabs.update(tabId, { url, active: true });
    await settle(tabId);
    return true;
  },
  async page({ name, params, settle: wait }) {
    const allowed = ['snapshot', 'click', 'type', 'pressEnter', 'choose', 'scroll'];
    if (!allowed.includes(name)) throw new Error('Unknown page action');
    const tabId = await harikaTab();
    const result = await onPage(tabId, name, params || []);
    if (wait) await settle(tabId);
    return result;
  },
  async back() {
    const tabId = await harikaTab();
    await chrome.tabs.goBack(tabId);
    await settle(tabId);
    return true;
  },
};

async function handle(ws, message) {
  try {
    const command = COMMANDS[message.cmd];
    if (!command) throw new Error('Unknown command');
    const result = await command(message.args || {});
    ws.send(JSON.stringify({ id: message.id, ok: true, result }));
  } catch (error) {
    ws.send(JSON.stringify({ id: message.id, ok: false, error: String(error?.message || error) }));
  }
}
