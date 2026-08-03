export interface BrowserInfo {
  name: 'chrome' | 'edge' | 'safari' | 'firefox' | 'other';
  isChrome: boolean;
  isEdge: boolean;
}

export function detectBrowser(): BrowserInfo {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return { name: 'other', isChrome: false, isEdge: false };
  }

  const ua = navigator.userAgent;
  const isEdge = /Edg\//i.test(ua);
  const isChrome = /Chrome/i.test(ua) && !isEdge;

  if (isEdge) return { name: 'edge', isChrome: false, isEdge: true };
  if (isChrome) return { name: 'chrome', isChrome: true, isEdge: false };
  if (/Safari/i.test(ua)) return { name: 'safari', isChrome: false, isEdge: false };
  if (/Firefox/i.test(ua)) return { name: 'firefox', isChrome: false, isEdge: false };

  return { name: 'other', isChrome: false, isEdge: false };
}
