// HARIKA's eyes and hands on a web page, for website tasks. One copy runs in HARIKA's own
// browser window (via DevTools) and the same file ships in HARIKA's browser extension.
//
// snapshot() numbers the visible things a person could click, type in or choose, and
// returns them with the page's readable text. Actions then name an element by that
// number. Nothing here reads cookies, storage or other tabs, and password and card
// fields are reported as sensitive (their contents are never read).
(() => {
  if (window.__harika && window.__harika.version === 3) return;

  const MAX_ELEMENTS = 160;
  const MAX_TEXT = 3500;
  const INTERACTIVE = 'a[href], button, input, textarea, select, summary, [role=button], [role=link], [role=checkbox], ' +
    '[role=radio], [role=tab], [role=menuitem], [role=option], [role=combobox], [role=textbox], [role=searchbox], ' +
    '[role=switch], [contenteditable=""], [contenteditable=true], [tabindex]:not([tabindex="-1"])';
  const SENSITIVE_AUTOCOMPLETE = /(^|\s)(current-password|new-password|one-time-code|cc-number|cc-csc|cc-exp|cc-exp-month|cc-exp-year)(\s|$)/;
  const SENSITIVE_NAME = /pass(word|code)?|pwd|otp|cvv|cvc|card.?num|ccnum|security.?code|pin\b|aadhaa?r|\bpan\b|ssn|iban|account.?num/i;

  let elements = new Map();

  function visible(el) {
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    if (rect.bottom < -200 || rect.top > innerHeight + 600) return false; // near the visible part of the page
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity) > 0.05;
  }

  function clean(text, limit = 90) {
    return (text || '').replace(/\s+/g, ' ').trim().slice(0, limit);
  }

  function labelOf(el) {
    const aria = el.getAttribute('aria-label') || '';
    const labelledBy = el.getAttribute('aria-labelledby');
    const byId = labelledBy ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.innerText || '').join(' ') : '';
    const forLabel = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText : '';
    const wrapping = el.closest('label')?.innerText || '';
    const own = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' ? '' : el.innerText;
    return clean(aria || byId || forLabel || own || wrapping || el.getAttribute('placeholder') || el.getAttribute('title') ||
      el.getAttribute('alt') || el.querySelector('img[alt]')?.getAttribute('alt') || el.getAttribute('name') ||
      (el.type === 'submit' || el.type === 'button' ? el.value : ''));
  }

  function isSensitive(el) {
    if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') return false;
    if (el.type === 'password') return true;
    if (SENSITIVE_AUTOCOMPLETE.test(el.getAttribute('autocomplete') || '')) return true;
    return SENSITIVE_NAME.test(`${el.name || ''} ${el.id || ''} ${el.getAttribute('placeholder') || ''} ${labelOf(el)}`);
  }

  function formOf(el) {
    const form = el.form || el.closest('form');
    if (!form) return null;
    const method = (form.getAttribute('method') || 'get').toLowerCase();
    const searchy = form.getAttribute('role') === 'search' || !!form.querySelector('input[type=search]');
    return { method, search: searchy };
  }

  function describe(el, id) {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'select' ? 'select' :
      tag === 'textarea' || el.isContentEditable ? 'textbox' : tag === 'input' ? (el.type || 'text') : tag);
    const item = { id, role, label: labelOf(el) };
    const sensitive = isSensitive(el);
    if (sensitive) item.sensitive = true;
    if (tag === 'input' || tag === 'textarea') {
      if (!sensitive && el.type !== 'checkbox' && el.type !== 'radio') item.value = clean(el.value, 60);
      if (el.type === 'checkbox' || el.type === 'radio') item.checked = el.checked;
    }
    if (tag === 'select') {
      item.value = clean(el.selectedOptions[0]?.text, 40);
      item.options = [...el.options].slice(0, 25).map((o) => clean(o.text, 40));
    }
    if (tag === 'a') item.href = clean(el.href, 120);
    const form = formOf(el);
    const submits = (tag === 'button' && (el.type || 'submit') === 'submit') || (tag === 'input' && (el.type === 'submit' || el.type === 'image'));
    if (form) item.form = form.method === 'post' && !form.search ? 'post' : 'get';
    if (submits) item.submits = true;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') item.disabled = true;
    return item;
  }

  function snapshot() {
    elements = new Map();
    const found = [];
    for (const el of document.querySelectorAll(INTERACTIVE)) {
      if (found.length >= MAX_ELEMENTS) break;
      if (!visible(el) || el.closest('[aria-hidden=true]')) continue;
      if (el.tagName === 'INPUT' && el.type === 'hidden') continue;
      const id = found.length + 1;
      elements.set(id, el);
      found.push(describe(el, id));
    }
    const main = document.querySelector('main, [role=main], article') || document.body;
    const captcha = !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="challenges.cloudflare"], .g-recaptcha, .h-captcha, .cf-turnstile');
    return {
      url: location.href,
      title: document.title,
      elements: found,
      text: clean(main ? main.innerText : '', MAX_TEXT),
      password_field: found.some((e) => e.role === 'password'),
      captcha,
      scroll: { at: Math.round(scrollY), height: Math.round(document.documentElement.scrollHeight), view: innerHeight },
    };
  }

  function element(id) {
    const el = elements.get(Number(id));
    if (!el || !el.isConnected) throw new Error('That element is no longer on the page');
    return el;
  }

  function center(id) {
    const el = element(id);
    el.scrollIntoView({ block: 'center', inline: 'center' });
    const rect = el.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }

  function click(id) {
    const el = element(id);
    el.scrollIntoView({ block: 'center' });
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
      el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    }
    el.click();
    return true;
  }

  function focus(id, clear) {
    const el = element(id);
    if (isSensitive(el)) throw new Error('HARIKA never types into password or payment fields');
    el.scrollIntoView({ block: 'center' });
    el.focus();
    if (clear) {
      if (el.isContentEditable) document.execCommand('selectAll');
      else if (typeof el.select === 'function') el.select();
    }
    return true;
  }

  function type(id, text) {
    const el = element(id);
    focus(id, true);
    if (el.isContentEditable) {
      document.execCommand('insertText', false, text);
    } else {
      // The native setter, so pages built with React and similar notice the change.
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return true;
  }

  function pressEnter(id) {
    const el = element(id);
    for (const kind of ['keydown', 'keypress', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(kind, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    }
    const form = el.form || el.closest('form');
    if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
    return true;
  }

  function choose(id, option) {
    const el = element(id);
    if (el.tagName !== 'SELECT') throw new Error('That element is not a list to choose from');
    const wanted = String(option).toLowerCase().trim();
    const match = [...el.options].find((o) => o.text.toLowerCase().trim() === wanted) ||
      [...el.options].find((o) => o.text.toLowerCase().includes(wanted));
    if (!match) throw new Error(`No option called "${option}"`);
    el.value = match.value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return match.text;
  }

  function scroll(direction) {
    window.scrollBy({ top: (direction === 'up' ? -1 : 1) * innerHeight * 0.85, behavior: 'instant' });
    return Math.round(scrollY);
  }

  function ready() {
    return document.readyState;
  }

  window.__harika = { version: 3, snapshot, click, center, focus, type, pressEnter, choose, scroll, ready };
})();
