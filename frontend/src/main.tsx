import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { OrbApp } from './features/orb/OrbApp';
import './index.css';

// The desktop shell opens a second, transparent window at index.html?window=orb.
const isOrbWindow = new URLSearchParams(window.location.search).get('window') === 'orb';
if (isOrbWindow) {
  document.body.classList.remove('bg-[#050608]');
  document.body.style.background = 'transparent';
  document.documentElement.style.background = 'transparent';
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>{isOrbWindow ? <OrbApp /> : <App />}</StrictMode>
);
