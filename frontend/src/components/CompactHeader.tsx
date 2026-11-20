import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';
import { ProfileSettingsModal } from './ProfileSettingsModal';

export const CompactHeader: React.FC = () => {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    profileStorage.getProfile().then(setProfile);
    const unsubscribe = profileStorage.onProfileChange(setProfile);
    return unsubscribe;
  }, []);

  return (
    <>
      <header className="sticky top-0 z-50 w-full pt-safe bg-surface/90 backdrop-blur-xl shadow-[0_1px_6px_rgba(0,0,0,0.04)] border-b border-surface-container-high/60 transition-colors">
        <div className="mx-auto flex h-14 sm:h-16 w-full max-w-4xl items-center justify-between px-3.5 sm:px-6">
          {/* Brand Logo & Offline Pill */}
          <Link to="/" className="flex items-center gap-2 transition hover:opacity-90 shrink-0">
            <img
              src="/logo.png"
              alt="DocMorph"
              className="h-7 w-7 sm:h-8 sm:w-8 rounded-xl object-cover shadow-sm shadow-primary/20"
            />
            <div className="flex items-center gap-1.5">
              <span className="text-base sm:text-lg font-bold text-on-surface tracking-tight">DocMorph</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant text-[10px] uppercase tracking-wider font-semibold">
                Offline
              </span>
            </div>
          </Link>

          {/* Quick Profile Access Capsule */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-1.5 sm:gap-2 rounded-full bg-surface-container-lowest/90 px-2.5 sm:px-3 py-1 shadow-[0_2px_8px_rgba(15,23,42,0.06)] border border-surface-container-high hover:border-primary/40 transition-all active:scale-95 shrink-0"
            title="Profile & Settings"
          >
            <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-primary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-on-primary text-[13px] sm:text-[14px]">person</span>
            </div>
            <span className="text-xs sm:text-sm text-on-surface font-medium max-w-[85px] xs:max-w-[120px] truncate">
              {profile?.full_name ? profile.full_name.split(' ')[0] : 'Profile'}
            </span>
            <span className="material-symbols-outlined text-outline text-[14px] sm:text-[16px]">settings</span>
          </button>
        </div>
      </header>

      {/* Settings Modal */}
      <ProfileSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onProfileUpdated={setProfile}
      />
    </>
  );
};
