import React from 'react';

interface GreetingProps {
  text: string;
  subtext?: string;
}

export const Greeting: React.FC<GreetingProps> = ({ text, subtext }) => {
  return (
    <div className="text-center space-y-3 px-6 select-none animate-in fade-in zoom-in-95 duration-700">
      <h1 className="text-3xl sm:text-4xl font-light tracking-wide text-slate-100 font-heading">
        {text}
      </h1>
      {subtext && (
        <p className="text-xs font-mono tracking-widest text-slate-400 uppercase">
          {subtext}
        </p>
      )}
    </div>
  );
};
