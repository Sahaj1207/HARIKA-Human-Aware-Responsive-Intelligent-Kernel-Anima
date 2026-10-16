import React, { useState } from 'react';

interface NameInputProps {
  onSubmit: (name: string) => void;
}

export const NameInput: React.FC<NameInputProps> = ({ onSubmit }) => {
  const [name, setName] = useState('');

  const trimmed = name.trim();
  const isValid = trimmed.length > 0 && trimmed.length <= 30;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isValid) onSubmit(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xs mx-auto flex flex-col items-center gap-6 bubble-enter">
      <input
        type="text"
        value={name}
        maxLength={30}
        onChange={(e) => setName(e.target.value)}
        placeholder="Your name"
        aria-label="Your name"
        autoFocus
        autoComplete="given-name"
        className="w-full rounded-xl bg-fill px-4 py-3 text-center t-headline text-label placeholder:text-label-3 placeholder:font-normal outline-none focus:ring-2 focus:ring-accent/60 transition"
      />
      <button
        type="submit"
        disabled={!isValid}
        className="w-full rounded-xl bg-accent text-white py-3 t-headline transition active:scale-[0.99] disabled:bg-fill disabled:text-label-3"
      >
        Continue
      </button>
    </form>
  );
};
