export const MotionPresets = {
  fadeIn: 'animate-in fade-in duration-200',
  fadeOut: 'animate-out fade-out duration-200',
  slideInRight: 'animate-in slide-in-from-right duration-300',
  slideInBottom: 'animate-in slide-in-from-bottom duration-300',
  scaleIn: 'animate-in zoom-in-95 duration-200',
  scaleOut: 'animate-out zoom-out-95 duration-200',
  glowPulse: 'animate-pulse transition-shadow duration-1000',
  coreBreathing: 'crystal-breathing 4s ease-in-out infinite',
  speakingWave: 'crystal-speaking 1.2s ease-in-out infinite',
  listeningPulse: 'crystal-listening 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
  thinkingSpin: 'animate-spin duration-1000 linear infinite',
} as const;

export type MotionPresetsType = typeof MotionPresets;
