import React from 'react';
import { OnboardingScreen } from '@/features/onboarding/OnboardingScreen';

interface StartupSequenceProps {
  onComplete?: () => void;
}

/**
 * StartupSequence — Delegates system boot & onboarding experience to OnboardingScreen.
 */
export const StartupSequence: React.FC<StartupSequenceProps> = ({ onComplete }) => {
  return <OnboardingScreen onComplete={onComplete || (() => {})} />;
};
