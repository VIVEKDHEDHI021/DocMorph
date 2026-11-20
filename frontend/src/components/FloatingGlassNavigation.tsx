import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { IridescentAddButton } from './IridescentAddButton';
import { NativeService } from '../services/nativeService';

interface FloatingGlassNavigationProps {
  onAddPdf?: () => void;
}

export const FloatingGlassNavigation: React.FC<FloatingGlassNavigationProps> = ({
  onAddPdf,
}) => {
  const location = useLocation();
  const navigate = useNavigate();

  const isHome = location.pathname === '/' || location.pathname === '/home' || location.pathname === '/dashboard';
  const isHistory = location.pathname === '/history';

  const handleHomeClick = () => {
    if (!isHome) {
      navigate('/');
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleHistoryClick = () => {
    if (!isHistory) {
      navigate('/history');
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleDefaultAddPdf = async () => {
    if (onAddPdf) {
      onAddPdf();
      return;
    }
    try {
      const picked = await NativeService.pickPdfFile();
      if (picked && picked.file) {
        window.dispatchEvent(new CustomEvent('docmorph:add-pdf', { detail: picked.file }));
      }
    } catch (err: any) {
      console.error('PDF selection cancelled or failed:', err);
    }
  };

  return (
    <div className="fixed bottom-4 sm:bottom-6 left-1/2 -translate-x-1/2 z-40 w-[88%] max-w-[300px] pointer-events-none pb-safe">
      <nav
        aria-label="Floating Navigation Capsule"
        className="pointer-events-auto relative flex h-14 sm:h-16 items-center justify-between rounded-full px-7 glass-capsule transition-all duration-300 shadow-[0_10px_28px_-6px_rgba(15,23,42,0.14)] border border-white/70"
      >
        {/* Home Button (Left) */}
        <button
          type="button"
          onClick={handleHomeClick}
          aria-label="Home"
          className={`group relative flex flex-col items-center justify-center p-2 transition-colors ${
            isHome ? 'text-primary' : 'text-on-surface-variant hover:text-primary'
          }`}
        >
          <span className="material-symbols-outlined text-[22px] sm:text-[24px]">home</span>
          {isHome && (
            <span className="absolute -bottom-1 h-1 w-2 rounded-full bg-primary shadow-sm shadow-primary" />
          )}
        </button>

        {/* Central Elevated Iridescent Add PDF Button (Center) */}
        <div>
          <IridescentAddButton onClick={handleDefaultAddPdf} />
        </div>

        {/* History Button (Right - replaces Profile) */}
        <button
          type="button"
          onClick={handleHistoryClick}
          aria-label="History"
          className={`group relative flex flex-col items-center justify-center p-2 transition-colors ${
            isHistory ? 'text-primary' : 'text-on-surface-variant hover:text-primary'
          }`}
        >
          <span className="material-symbols-outlined text-[22px] sm:text-[24px]">history</span>
          {isHistory && (
            <span className="absolute -bottom-1 h-1 w-2 rounded-full bg-primary shadow-sm shadow-primary" />
          )}
        </button>
      </nav>
    </div>
  );
};
