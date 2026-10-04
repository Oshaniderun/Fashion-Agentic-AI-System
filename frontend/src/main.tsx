import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles/theme.css';
import './index.css';

const bgImage = (import.meta.env.VITE_APP_BG_IMAGE as string | undefined)?.trim();
if (bgImage) {
  document.documentElement.style.setProperty('--app-bg-image', `url("${bgImage.replace(/["']/g, '')}")`);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
