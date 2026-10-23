import React from 'react';
import { Button } from '@/components/apple/controls';
import { askHarika } from '@/components/apple/MessageList';

const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);

/** The last step: things to try, chosen from what was just set up. Tapping one asks HARIKA. */
export const TryItSetup: React.FC<{ name: string; google: boolean; onDone: () => void }> = ({ name, google, onDone }) => {
  const ideas = [
    google ? "What's on my calendar today?" : "How's the weather today?",
    'Remind me to stretch in 20 minutes',
    'Play some lofi on YouTube',
    "What's the latest news?",
    'Compare the best 3 laptops under 60k for coding',
  ];

  const tryIt = (text: string) => {
    onDone();
    setTimeout(() => askHarika(text), 300);
  };

  return (
    <div className="w-full max-w-xl space-y-6 bubble-enter text-center">
      <div className="space-y-2">
        <h1 className="t-large-title text-label">You're all set{name ? `, ${name}` : ''}.</h1>
        <p className="t-body text-label-2">
          Talk to me in your own words. Try one of these, or press {isMac ? '⌃ ⇧ Space' : 'Ctrl + Shift + Space'} in any app.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {ideas.map((idea) => (
          <button
            key={idea}
            type="button"
            onClick={() => tryIt(idea)}
            className="glass rounded-full px-4 py-2 t-callout text-label hover:brightness-105 active:scale-[0.98] transition"
          >
            {idea}
          </button>
        ))}
      </div>
      <Button kind="plain" onClick={onDone}>Start using HARIKA</Button>
    </div>
  );
};
