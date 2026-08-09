import React, { useState } from 'react';
import { themeEngine, ThemeMode } from '../theme/themeEngine';
import { CrystalButton } from '../components/CrystalButton';
import { CrystalCard } from '../components/CrystalCard';
import { Moon, Sun, Monitor, Download, Upload, RotateCcw } from 'lucide-react';
import { notificationService } from '../notifications/notificationService';

export const AppearanceSettings: React.FC = () => {
  const [config, setConfig] = useState(themeEngine.getConfig());

  const handleModeChange = (mode: ThemeMode) => {
    const updated = themeEngine.setMode(mode);
    setConfig(updated);
    notificationService.showInfo('Theme Updated', `Switched theme to ${mode} mode.`);
  };

  const handleContrastToggle = () => {
    const updated = themeEngine.setHighContrast(!config.highContrast);
    setConfig(updated);
  };

  const handleMotionToggle = () => {
    const updated = themeEngine.setReducedMotion(!config.reducedMotion);
    setConfig(updated);
  };

  const handleExport = () => {
    const json = themeEngine.exportSettings();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'harika_crystal_settings.json';
    a.click();
    URL.revokeObjectURL(url);
    notificationService.showSuccess('Settings Exported', 'Downloaded harika_crystal_settings.json');
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      if (text) {
        const updated = themeEngine.importSettings(text);
        setConfig(updated);
        notificationService.showSuccess('Settings Imported', 'Successfully imported settings.');
      }
    };
    reader.readAsText(file);
  };

  const handleReset = () => {
    const updated = themeEngine.resetSettings();
    setConfig(updated);
    notificationService.showWarning('Settings Reset', 'Restored default settings.');
  };

  return (
    <div className="space-y-4 font-mono">
      {/* Theme Mode Selector */}
      <div className="space-y-2">
        <label className="text-[10px] uppercase text-slate-400">Theme Mode</label>
        <div className="grid grid-cols-3 gap-2">
          <CrystalButton
            variant={config.mode === 'dark' ? 'primary' : 'secondary'}
            icon={<Moon className="w-3.5 h-3.5" />}
            onClick={() => handleModeChange('dark')}
          >
            Dark
          </CrystalButton>
          <CrystalButton
            variant={config.mode === 'light' ? 'primary' : 'secondary'}
            icon={<Sun className="w-3.5 h-3.5" />}
            onClick={() => handleModeChange('light')}
          >
            Light
          </CrystalButton>
          <CrystalButton
            variant={config.mode === 'system' ? 'primary' : 'secondary'}
            icon={<Monitor className="w-3.5 h-3.5" />}
            onClick={() => handleModeChange('system')}
          >
            System
          </CrystalButton>
        </div>
      </div>

      {/* Accessibility Toggles */}
      <CrystalCard className="space-y-2 p-3">
        <div className="flex items-center justify-between text-xs text-slate-200">
          <span>High Contrast Mode</span>
          <input
            type="checkbox"
            checked={config.highContrast}
            onChange={handleContrastToggle}
            className="cursor-pointer"
          />
        </div>
        <div className="flex items-center justify-between text-xs text-slate-200">
          <span>Reduced Motion</span>
          <input
            type="checkbox"
            checked={config.reducedMotion}
            onChange={handleMotionToggle}
            className="cursor-pointer"
          />
        </div>
      </CrystalCard>

      {/* Import / Export / Reset */}
      <div className="space-y-2 pt-2 border-t border-white/10">
        <label className="text-[10px] uppercase text-slate-400">Configuration Backup</label>
        <div className="flex items-center space-x-2">
          <CrystalButton variant="secondary" icon={<Download className="w-3.5 h-3.5" />} onClick={handleExport}>
            Export
          </CrystalButton>
          <label className="cursor-pointer">
            <span className="inline-flex items-center justify-center font-mono uppercase tracking-wider text-xs px-3.5 py-1.5 rounded-lg bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 space-x-1.5">
              <Upload className="w-3.5 h-3.5" />
              <span>Import</span>
            </span>
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
          </label>
          <CrystalButton variant="danger" icon={<RotateCcw className="w-3.5 h-3.5" />} onClick={handleReset}>
            Reset
          </CrystalButton>
        </div>
      </div>
    </div>
  );
};
