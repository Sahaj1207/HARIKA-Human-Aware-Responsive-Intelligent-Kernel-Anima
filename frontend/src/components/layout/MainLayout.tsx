import React, { useState, useEffect } from 'react';
import { HARIKACore } from '../core/HARIKACore';
import { ConversationCanvas } from '../core/ConversationCanvas';
import { CommandBar } from '../core/CommandBar';
import { StatusBar } from '../core/StatusBar';
import { QuickPanel } from '../core/QuickPanel';
import { StartupSequence } from '../core/StartupSequence';
import { useHARIKAStore } from '@/store/useHARIKAStore';

// Crystal Core Imports
import { ErrorBoundary } from '@/core/crystal/accessibility/ErrorBoundary';
import { CommandPalette } from '@/core/crystal/shortcuts/CommandPalette';
import { SettingsCenter } from '@/core/crystal/settings/SettingsCenter';
import { DebugOverlay } from '@/core/crystal/developer/DebugOverlay';
import { NotificationToastContainer } from '@/core/crystal/notifications/NotificationToastContainer';
import { useKeyboardShortcuts } from '@/core/crystal/shortcuts/useKeyboardShortcuts';
import { initializeCrystalCore } from '@/core/crystal/crystalInit';
import { useLiveEvents } from '@/hooks/useLiveEvents';
import '@/core/crystal/motion/animations.css';

export const MainLayout: React.FC = () => {
  const { coreState, isBooted } = useHARIKAStore();
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDebugOverlayVisible, setIsDebugOverlayVisible] = useState(false);

  useLiveEvents();

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
      <div className="relative w-screen h-screen bg-[#050608] ambient-bg-glow flex flex-col justify-between overflow-hidden select-none">
        {/* Startup sequence overlay */}
        {!isBooted && <StartupSequence />}

        {/* Top Subtle Status Bar Overlay */}
        <StatusBar />

        {/* Center Viewport Focus: Decoupled AI Core Engine */}
        <main className="flex-1 flex flex-col items-center justify-between py-4 relative z-10 overflow-hidden">
          {/* Core Centerpiece Visual */}
          <div className="my-auto py-6 flex flex-col items-center justify-center transition-all duration-700">
            <HARIKACore state={coreState} size={240} intensity={1.0} />
          </div>

          {/* Spatial Conversation Canvas */}
          <ConversationCanvas />

          {/* Floating OS Command Bar */}
          <CommandBar />
        </main>

        {/* Hidden Quick Controls Slide-Over Panel */}
        <QuickPanel />

        {/* Crystal Core Universal Overlays & Notifications */}
        <CommandPalette isOpen={isCommandPaletteOpen} onClose={() => setIsCommandPaletteOpen(false)} />
        <SettingsCenter isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
        <DebugOverlay visible={isDebugOverlayVisible} />
        <NotificationToastContainer />
      </div>
    </ErrorBoundary>
  );
};

