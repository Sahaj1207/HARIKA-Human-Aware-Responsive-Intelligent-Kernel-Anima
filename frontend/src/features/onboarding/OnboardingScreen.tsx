import React, { useEffect, useState } from 'react';
import { Greeting } from './Greeting';
import { NameInput } from './NameInput';
import { userStorage, UserProfile } from './storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { HarikaOrb } from '@/components/apple/HarikaOrb';
import { BrainSetup } from './BrainSetup';
import { ExtrasSetup } from './ExtrasSetup';
import { TryItSetup } from './TryItSetup';

interface OnboardingScreenProps {
  onComplete: () => void;
  /** "Run setup again" from Settings starts at the brain step for someone HARIKA already knows. */
  startAt?: 'step-brain';
}

type OnboardingStep =
  | 'detecting'
  | 'returning-greeting'
  | 'step-hello'
  | 'step-identity'
  | 'step-ask-name'
  | 'step-brain'
  | 'step-extras'
  | 'step-try'
  | 'step-welcome-user'
  | 'finished';

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ onComplete, startAt }) => {
  const setCoreState = useHARIKAStore((s) => s.setCoreState);
  const setIsBooted = useHARIKAStore((s) => s.setIsBooted);

  const [step, setStep] = useState<OnboardingStep>('detecting');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [google, setGoogle] = useState(false);

  useEffect(() => {
    const existing = userStorage.getProfile();

    if (startAt) {
      setProfile(existing);
      setCoreState('idle');
      setStep(startAt);
      return;
    }

    if (existing) {
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
      setCoreState('booting');
      setStep('step-hello');

      const t1 = setTimeout(() => {
        setStep('step-identity');
      }, 1400);

      const t2 = setTimeout(() => {
        setStep('step-ask-name');
        setCoreState('idle');
      }, 3600);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNameSubmit = (name: string) => {
    const newProfile = { name };
    userStorage.saveProfile(newProfile);
    setProfile(newProfile);
    setStep('step-brain');
  };

  const finish = () => {
    setCoreState('idle');
    setStep('finished');
    setIsBooted(true);
    onComplete();
  };

  if (step === 'finished') return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-canvas">
      <div className="flex flex-col items-center justify-center gap-8 max-w-2xl w-full px-6">
        {!['step-brain', 'step-extras', 'step-try'].includes(step) && <HarikaOrb size={step === 'step-ask-name' ? 96 : 128} state={step === 'step-welcome-user' ? 'speaking' : 'idle'} />}

        {step === 'returning-greeting' && profile && (
          <Greeting text={`Hello, ${profile.name}.`} subtext="Welcome back." />
        )}

        {step === 'step-hello' && <Greeting text="Hello." />}

        {step === 'step-identity' && (
          <Greeting text="I'm HARIKA." subtext="I can open your apps, find your files, set reminders and answer questions." />
        )}

        {step === 'step-ask-name' && (
          <div className="space-y-8 w-full text-center">
            <Greeting text="What should I call you?" />
            <NameInput onSubmit={handleNameSubmit} />
          </div>
        )}

        {step === 'step-brain' && <BrainSetup onDone={() => setStep('step-extras')} />}

        {step === 'step-extras' && (
          <ExtrasSetup
            onDone={(state) => {
              setGoogle(state.google);
              setStep('step-try');
            }}
          />
        )}

        {step === 'step-try' && <TryItSetup name={profile?.name ?? ''} google={google} onDone={finish} />}

        {step === 'step-welcome-user' && profile && (
          <Greeting text={`Nice to meet you, ${profile.name}.`} subtext="Ask me anything, from here or from any app." />
        )}
      </div>
    </div>
  );
};
