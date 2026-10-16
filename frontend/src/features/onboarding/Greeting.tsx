import React from 'react';

interface GreetingProps {
  text: string;
  subtext?: string;
}

export const Greeting: React.FC<GreetingProps> = ({ text, subtext }) => {
  return (
    <div className="text-center space-y-2 select-none bubble-enter text-balance">
      <h1 className="t-large-title text-label">{text}</h1>
      {subtext && <p className="t-body text-label-2">{subtext}</p>}
    </div>
  );
};
