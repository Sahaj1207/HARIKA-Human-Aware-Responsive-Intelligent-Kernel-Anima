import { useEffect } from 'react';

export interface ShortcutHandlers {
  onOpenCommandPalette?: () => void;
  onOpenSettings?: () => void;
  onCloseOverlay?: () => void;
  onQuickHelp?: () => void;
}

export const useKeyboardShortcuts = (handlers: ShortcutHandlers) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K or Ctrl+Shift+P -> Open Command Palette
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || (e.shiftKey && e.key === 'P'))) {
        e.preventDefault();
        handlers.onOpenCommandPalette?.();
      }
      // Ctrl+/ -> Quick Help
      else if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        handlers.onQuickHelp?.();
      }
      // Escape -> Close overlays
      else if (e.key === 'Escape') {
        handlers.onCloseOverlay?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlers]);
};
