export class AccessibilityManager {
  public static setFocus(elementId: string): void {
    const el = document.getElementById(elementId);
    if (el) el.focus();
  }

  public static announceARIA(message: string): void {
    let liveRegion = document.getElementById('crystal-aria-live');
    if (!liveRegion) {
      liveRegion = document.createElement('div');
      liveRegion.id = 'crystal-aria-live';
      liveRegion.setAttribute('aria-live', 'polite');
      liveRegion.setAttribute('aria-atomic', 'true');
      liveRegion.className = 'sr-only';
      document.body.appendChild(liveRegion);
    }
    liveRegion.textContent = message;
  }

  public static isReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
}
