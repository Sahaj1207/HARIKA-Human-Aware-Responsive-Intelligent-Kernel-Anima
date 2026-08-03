import React, { useEffect, useState } from 'react';
import { Greeting } from './Greeting';
import { NameInput } from './NameInput';
import { userStorage, UserProfile } from './storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';

interface OnboardingScreenProps {
  onComplete: () => void;
}

type OnboardingStep =
  | 'detecting'
  | 'returning-greeting'
  | 'step-hello'
  | 'step-identity'
  | 'step-ask-name'
  | 'step-welcome-user'
  | 'finished';

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ onComplete }) => {
  // Use Zustand selector functions to avoid re-rendering OnboardingScreen on every global state change
  const setCoreState = useHARIKAStore((s) => s.setCoreState);
  const setIsBooted = useHARIKAStore((s) => s.setIsBooted);
  const addMessage = useHARIKAStore((s) => s.addMessage);

  const [step, setStep] = useState<OnboardingStep>('detecting');
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    const existing = userStorage.getProfile();

    if (existing) {
      // Returning User Flow
      setProfile(existing);
      setStep('returning-greeting');
      setCoreState('idle');

      const timer = setTimeout(() => {
        setStep('finished');
        setIsBooted(true);
        onComplete();
      }, 1800);

      return () => clearTimeout(timer);
    } else {
      // First-Launch Onboarding Sequence
      setCoreState('booting');
      setStep('step-hello');

      const t1 = setTimeout(() => {
        setStep('step-identity');
      }, 1400);

      const t2 = setTimeout(() => {
        setStep('step-ask-name');
        setCoreState('idle');
      }, 2800);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }

    // Run once on component mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNameSubmit = (name: string) => {
    const newProfile = { name };
    userStorage.saveProfile(newProfile);
    setProfile(newProfile);

    // Add initial welcome message to conversation canvas
    addMessage({
      sender: 'harika',
      content: `Welcome to HARIKA OS, ${name}. All neural subsystems are online.`,
    });

    setStep('step-welcome-user');
    setCoreState('speaking');

    setTimeout(() => {
      setCoreState('idle');
      setStep('finished');
      setIsBooted(true);
      onComplete();
    }, 2000);
  };

  if (step === 'finished') return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#050608] transition-opacity duration-1000">
      <div className="flex flex-col items-center justify-center space-y-8 max-w-md w-full px-6">
        {step === 'returning-greeting' && profile && (
          <Greeting text={`Hello, ${profile.name}.`} subtext="HARIKA OS Ready" />
        )}

        {step === 'step-hello' && <Greeting text="Hello." />}

        {step === 'step-identity' && (
          <Greeting text="I'm HARIKA." subtext="AI Operating System" />
        )}

        {step === 'step-ask-name' && (
          <div className="space-y-6 w-full text-center">
            <Greeting text="What should I call you?" />
            <NameInput onSubmit={handleNameSubmit} />
          </div>
        )}

        {step === 'step-welcome-user' && profile && (
          <Greeting text={`Nice to meet you, ${profile.name}.`} subtext="Initializing Workspace" />
        )}
      </div>
    </div>
  );
};
