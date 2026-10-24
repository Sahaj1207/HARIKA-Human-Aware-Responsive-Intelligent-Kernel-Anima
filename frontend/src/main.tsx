import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { OrbApp } from './features/orb/OrbApp';
import { GlowApp } from './features/glow/GlowApp';
import './core/crystal/theme/themeEngine'; // applies Automatic / Light / Dark before first paint
import './index.css';

// The desktop shell opens transparent windows at index.html?window=orb and ?window=glow.
const windowKind = new URLSearchParams(window.location.search).get('window');
const isOrbWindow = windowKind === 'orb';
const isGlowWindow = windowKind === 'glow';
if (isOrbWindow || isGlowWindow) {
  document.body.style.background = 'transparent';
  document.documentElement.style.background = 'transparent';
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>{isGlowWindow ? <GlowApp /> : isOrbWindow ? <OrbApp /> : <App />}</StrictMode>
);
