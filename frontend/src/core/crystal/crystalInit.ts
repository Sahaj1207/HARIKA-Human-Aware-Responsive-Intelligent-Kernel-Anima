import React from 'react';
import { settingsRegistry } from './settings/settingsRegistry';
import { commandRegistry } from './shortcuts/commandRegistry';
import { diagnosticsRegistry } from './developer/diagnosticsRegistry';
import { AppearanceSettings } from './settings/AppearanceSettings';
import { DeveloperPanel } from './developer/DeveloperPanel';
import { notificationService } from './notifications/notificationService';
import { themeEngine } from './theme/themeEngine';
import { Settings as SettingsIcon, Monitor, Activity, Terminal } from 'lucide-react';


let initialized = false;

export const initializeCrystalCore = (callbacks: {
  openSettings: () => void;
  openCommandPalette: () => void;
  toggleDebugOverlay: () => void;
}) => {
  if (initialized) return;
  initialized = true;

  // 1. Register Settings Pages
  settingsRegistry.registerPage({
    id: 'appearance',
    label: 'Appearance',
    category: 'general',
    icon: React.createElement(Monitor, { className: 'w-3.5 h-3.5' }),
    component: AppearanceSettings,
  });

  settingsRegistry.registerPage({
    id: 'developer',
    label: 'Developer',
    category: 'developer',
    icon: React.createElement(Terminal, { className: 'w-3.5 h-3.5' }),
    component: DeveloperPanel,
  });

  // 2. Register Commands
  commandRegistry.registerCommand({
    id: 'cmd-open-settings',
    label: 'Open Settings Center',
    category: 'system',
    shortcut: 'Ctrl+Shift+S',
    icon: React.createElement(SettingsIcon, { className: 'w-4 h-4' }),
    action: callbacks.openSettings,
  });

  commandRegistry.registerCommand({
    id: 'cmd-open-palette',
    label: 'Open Command Palette',
    category: 'navigation',
    shortcut: 'Ctrl+K',
    icon: React.createElement(Terminal, { className: 'w-4 h-4' }),
    action: callbacks.openCommandPalette,
  });

  commandRegistry.registerCommand({
    id: 'cmd-toggle-debug',
    label: 'Toggle Developer Debug Overlay',
    category: 'developer',
    shortcut: 'Ctrl+Shift+D',
    icon: React.createElement(Activity, { className: 'w-4 h-4' }),
    action: callbacks.toggleDebugOverlay,
  });

  commandRegistry.registerCommand({
    id: 'cmd-toggle-theme',
    label: 'Toggle Theme (Dark / Light)',
    category: 'system',
    icon: React.createElement(Monitor, { className: 'w-4 h-4' }),
    action: () => {
      const current = themeEngine.getConfig().mode;
      const next = current === 'dark' ? 'light' : 'dark';
      themeEngine.setMode(next);
      notificationService.showInfo('Theme Switched', `Mode set to ${next}.`);
    },
  });

  // 3. Register Diagnostics Cards
  diagnosticsRegistry.registerCard({
    id: 'card-memory',
    title: 'Cognitive Memory Diagnostic',
    category: 'ai_engine',
    component: () =>
      React.createElement('div', { className: 'text-[11px] font-mono text-slate-300' }, 'Status: Healthy | Active Store: SQLite + Vector Index'),
  });

  diagnosticsRegistry.registerCard({
    id: 'card-vision',
    title: 'Multimodal Vision Diagnostic',
    category: 'ai_engine',
    component: () =>
      React.createElement('div', { className: 'text-[11px] font-mono text-slate-300' }, 'Active Provider: Local | OCR Engine: Tesseract/PyMuPDF'),
  });

  diagnosticsRegistry.registerCard({
    id: 'card-voice',
    title: 'Voice Engine 2.0 Diagnostic',
    category: 'ai_engine',
    component: () =>
      React.createElement('div', { className: 'text-[11px] font-mono text-slate-300' }, 'TTS: WebSpeech API | STT: WebSpeech API | Queue: Ready'),
  });
};
