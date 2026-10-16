import React, { useState, useEffect } from 'react';
import { MessageList } from '../apple/MessageList';
import { CommandBar } from '../core/CommandBar';
import { StatusBar } from '../core/StatusBar';
import { QuickPanel } from '../core/QuickPanel';
import { StartupSequence } from '../core/StartupSequence';
import { useHARIKAStore } from '@/store/useHARIKAStore';

// Crystal Core Imports
import { ErrorBoundary } from '@/core/crystal/accessibility/ErrorBoundary';
import { CommandPalette } from '@/core/crystal/shortcuts/CommandPalette';
import { SettingsWindow, SettingsPageId } from '@/features/settings/SettingsWindow';
import { DebugOverlay } from '@/core/crystal/developer/DebugOverlay';
import { NotificationToastContainer } from '@/core/crystal/notifications/NotificationToastContainer';
import { useKeyboardShortcuts } from '@/core/crystal/shortcuts/useKeyboardShortcuts';
import { initializeCrystalCore } from '@/core/crystal/crystalInit';
import { useLiveEvents } from '@/hooks/useLiveEvents';
import '@/core/crystal/motion/animations.css';

export const MainLayout: React.FC = () => {
  const isBooted = useHARIKAStore((s) => s.isBooted);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDebugOverlayVisible, setIsDebugOverlayVisible] = useState(false);
  const [settingsPage, setSettingsPage] = useState<SettingsPageId>('general');

  useLiveEvents();

  // Other parts of the app (e.g. onboarding) can open Settings on a given page.
  useEffect(() => {
    const open = (event: Event) => {
      setSettingsPage(((event as CustomEvent<SettingsPageId>).detail) || 'general');
      setIsSettingsOpen(true);
    };
    window.addEventListener('harika:open-settings', open);
    return () => window.removeEventListener('harika:open-settings', open);
  }, []);

  useEffect(() => {
    initializeCrystalCore({
      openSettings: () => setIsSettingsOpen(true),
      openCommandPalette: () => setIsCommandPaletteOpen(true),
      toggleDebugOverlay: () => setIsDebugOverlayVisible((prev) => !prev),
    });
  }, []);

  useKeyboardShortcuts({
    onOpenCommandPalette: () => setIsCommandPaletteOpen(true),
    onOpenSettings: () => setIsSettingsOpen(true),
    onCloseOverlay: () => {
      setIsCommandPaletteOpen(false);
      setIsSettingsOpen(false);
    },
  });

  return (
    <ErrorBoundary>
      <div className="relative w-screen h-screen bg-canvas text-label flex flex-col overflow-hidden">
        {!isBooted && <StartupSequence />}

        <StatusBar onOpenSettings={() => setIsSettingsOpen(true)} />

        <main className="relative flex-1 min-h-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-y-auto">
            <MessageList />
          </div>
          <CommandBar />
        </main>

        {/* Developer telemetry, opened from Settings > Developer */}
        <QuickPanel />

        <CommandPalette isOpen={isCommandPaletteOpen} onClose={() => setIsCommandPaletteOpen(false)} />
        <SettingsWindow
          isOpen={isSettingsOpen}
          initialPage={settingsPage}
          onClose={() => {
            setIsSettingsOpen(false);
            setSettingsPage('general');
          }}
        />
        <DebugOverlay visible={isDebugOverlayVisible} />
        <NotificationToastContainer />
      </div>
    </ErrorBoundary>
  );
};
