import React, { useState } from 'react';
import { ArrowRight } from 'lucide-react';

interface NameInputProps {
  onSubmit: (name: string) => void;
}

export const NameInput: React.FC<NameInputProps> = ({ onSubmit }) => {
  const [name, setName] = useState('');

  const trimmed = name.trim();
  const isValid = trimmed.length > 0 && trimmed.length <= 30;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isValid) {
      onSubmit(trimmed);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-sm mx-auto flex flex-col items-center space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-700"
    >
      <div className="relative w-full">
        <input
          type="text"
          value={name}
          maxLength={30}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter your name..."
          autoFocus
          className="w-full surface-translucent px-5 py-3.5 rounded-full text-center text-slate-100 placeholder-slate-500 font-sans text-base focus:outline-none focus:border-cyan-500/50 transition-all shadow-xl"
        />
        <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-mono text-slate-500">
          {name.length}/30
        </div>
      </div>

      <button
        type="submit"
        disabled={!isValid}
        className="inline-flex items-center space-x-2 px-6 py-2.5 rounded-full surface-translucent text-xs font-mono tracking-widest uppercase text-slate-200 hover:text-cyan-300 border border-white/10 hover:border-cyan-500/40 disabled:opacity-30 disabled:hover:border-white/10 disabled:hover:text-slate-200 transition-all cursor-pointer disabled:cursor-not-allowed shadow-lg"
      >
        <span>Continue</span>
        <ArrowRight className="w-3.5 h-3.5" />
      </button>
    </form>
  );
};
