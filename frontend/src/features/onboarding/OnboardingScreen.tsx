import React, { useEffect, useState } from 'react';
import { Greeting } from './Greeting';
import { NameInput } from './NameInput';
import { userStorage, UserProfile } from './storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { HarikaOrb } from '@/components/apple/HarikaOrb';
import { llmSettingsService } from '@/services/api/llmSettings';
import { BrainSetup } from './BrainSetup';

interface OnboardingScreenProps {
  onComplete: () => void;
}

type OnboardingStep =
  | 'detecting'
  | 'returning-greeting'
  | 'step-hello'
  | 'step-identity'
  | 'step-ask-name'
  | 'step-brain'
  | 'step-welcome-user'
  | 'finished';

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ onComplete }) => {
  const setCoreState = useHARIKAStore((s) => s.setCoreState);
  const setIsBooted = useHARIKAStore((s) => s.setIsBooted);

  const [step, setStep] = useState<OnboardingStep>('detecting');
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    const existing = userStorage.getProfile();

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

  const welcome = () => {
    setStep('step-welcome-user');
    setCoreState('speaking');

    setTimeout(() => {
      setCoreState('idle');
      setStep('finished');
      setIsBooted(true);
      onComplete();
    }, 2000);
  };

  const handleNameSubmit = async (name: string) => {
    const newProfile = { name };
    userStorage.saveProfile(newProfile);
    setProfile(newProfile);

    // A new computer often has no model yet; only then ask how HARIKA should think.
    try {
      const [settings, local] = await Promise.all([llmSettingsService.get(), llmSettingsService.localStatus()]);
      const usesCloud = Object.values(settings.roles).some((role) => !role.on_device);
      if (usesCloud || (local.running && local.has_recommended)) return welcome();
    } catch {
      // Engine still starting: offer the choice anyway.
    }
    setStep('step-brain');
  };

  const useCloud = () => {
    setStep('finished');
    setIsBooted(true);
    onComplete();
    window.dispatchEvent(new CustomEvent('harika:open-settings', { detail: 'brain' }));
  };

  if (step === 'finished') return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-canvas">
      <div className="flex flex-col items-center justify-center gap-8 max-w-2xl w-full px-6">
        {step !== 'step-brain' && <HarikaOrb size={step === 'step-ask-name' ? 96 : 128} state={step === 'step-welcome-user' ? 'speaking' : 'idle'} />}

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

        {step === 'step-brain' && <BrainSetup onDone={welcome} onUseCloud={useCloud} />}

        {step === 'step-welcome-user' && profile && (
          <Greeting text={`Nice to meet you, ${profile.name}.`} subtext="Ask me anything, from here or from any app." />
        )}
      </div>
    </div>
  );
};
