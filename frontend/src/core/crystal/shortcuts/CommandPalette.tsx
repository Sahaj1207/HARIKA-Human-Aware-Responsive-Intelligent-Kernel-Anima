import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';

import { commandRegistry, CommandItemContribution } from './commandRegistry';
import { CrystalDialog } from '../components/CrystalDialog';

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [commands, setCommands] = useState<CommandItemContribution[]>([]);

  useEffect(() => {
    if (isOpen) {
      setCommands(commandRegistry.getCommands());
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  const filteredCommands = commands.filter(
    (cmd) =>
      cmd.label.toLowerCase().includes(query.toLowerCase()) ||
      cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredCommands.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % Math.max(1, filteredCommands.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].action();
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <CrystalDialog isOpen={isOpen} onClose={onClose} title="Universal Command Palette">
      <div className="space-y-3" onKeyDown={handleKeyDown}>
        {/* Search input */}
        <div className="relative flex items-center">
          <Search className="w-4 h-4 absolute left-3 text-slate-400" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command or search..."
            className="w-full bg-slate-950/80 border border-white/10 rounded-xl pl-9 pr-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>

        {/* Commands List */}
        <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
          {filteredCommands.length === 0 ? (
            <div className="text-[11px] font-mono text-slate-500 italic p-3 text-center">
              No matching commands found.
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => (
              <button
                key={cmd.id}
                onClick={() => {
                  cmd.action();
                  onClose();
                }}
                className={`w-full flex items-center justify-between p-2.5 rounded-lg text-xs font-mono transition-all ${
                  idx === selectedIndex
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-300 hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className="flex items-center space-x-2">
                  {cmd.icon && <span className="text-cyan-400">{cmd.icon}</span>}
                  <span>{cmd.label}</span>
                </div>
                {cmd.shortcut && (
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-slate-400">
                    {cmd.shortcut}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </CrystalDialog>
  );
};
