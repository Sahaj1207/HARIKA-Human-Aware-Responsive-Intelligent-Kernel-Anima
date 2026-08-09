import React from 'react';

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

export interface CrystalTabsProps {
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export const CrystalTabs: React.FC<CrystalTabsProps> = ({ tabs, activeTab, onTabChange }) => {
  return (
    <div className="flex space-x-1 border-b border-white/10 pb-2 overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`px-3 py-1.5 rounded-lg text-[10px] font-mono tracking-wider uppercase flex items-center space-x-1.5 transition-colors ${
            activeTab === tab.id
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
          }`}
        >
          {tab.icon && <span>{tab.icon}</span>}
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
};
