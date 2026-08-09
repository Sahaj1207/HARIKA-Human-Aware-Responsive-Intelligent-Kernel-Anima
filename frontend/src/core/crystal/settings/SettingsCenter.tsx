import React, { useState } from 'react';
import { settingsRegistry } from './settingsRegistry';

import { CrystalPanel } from '../components/CrystalPanel';
import { CrystalTabs, TabItem } from '../components/CrystalTabs';
import { Settings as SettingsIcon } from 'lucide-react';

export interface SettingsCenterProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsCenter: React.FC<SettingsCenterProps> = ({ isOpen, onClose }) => {
  const pages = settingsRegistry.getPages();
  const [activePageId, setActivePageId] = useState<string>(pages[0]?.id || 'general');

  const tabItems: TabItem[] = pages.map((p) => ({
    id: p.id,
    label: p.label,
    icon: p.icon,
  }));

  const activePage = settingsRegistry.getPage(activePageId);

  return (
    <CrystalPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Settings Center"
      subtitle="Plugin-based HARIKA v1.0 Configuration"
      icon={<SettingsIcon className="w-4 h-4" />}
      width="w-full max-w-xl"
    >
      <div className="space-y-4">
        {/* Dynamic Registered Tabs */}
        {tabItems.length > 0 && (
          <CrystalTabs tabs={tabItems} activeTab={activePageId} onTabChange={setActivePageId} />
        )}

        {/* Page Content */}
        <div className="pt-2">
          {activePage ? (
            <activePage.component />
          ) : (
            <div className="text-xs font-mono text-slate-500 italic p-4 text-center">
              No registered settings page selected.
            </div>
          )}
        </div>
      </div>
    </CrystalPanel>
  );
};
