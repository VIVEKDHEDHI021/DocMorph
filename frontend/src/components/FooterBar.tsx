import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, Sparkles, Compass, LayoutDashboard, User } from 'lucide-react';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';
import { ProfileSettingsModal } from './ProfileSettingsModal';

export const FooterBar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    profileStorage.getProfile().then(setProfile);
    const unsubscribe = profileStorage.onProfileChange(setProfile);
    return unsubscribe;
  }, []);

  const scrollToSection = (sectionId: string) => {
    if (location.pathname === '/') {
      const el = document.getElementById(sectionId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
        window.history.pushState(null, '', `#${sectionId}`);
      }
    } else {
      navigate(`/#${sectionId}`);
    }
  };

  const isActive = (path: string, hash?: string) => {
    if (hash) {
      return location.pathname === '/' && location.hash === `#${hash}`;
    }
    return location.pathname === path && !location.hash;
  };

  return (
    <>
      <nav
        aria-label="Footer Navigation Bar"
        className="fixed bottom-0 inset-x-0 z-40 border-t border-slate-200/90 bg-white/95 backdrop-blur-lg shadow-[0_-4px_24px_rgba(15,23,42,0.06)] pb-[env(safe-area-inset-bottom)]"
      >
        <div className="mx-auto flex h-16 max-w-lg items-center justify-around px-2 sm:px-4">
          {/* Home */}
          <Link
            to="/"
            onClick={() => {
              if (location.pathname === '/') {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }
            }}
            className={`group flex flex-1 flex-col items-center justify-center py-1 transition-all ${
              isActive('/')
                ? 'text-brand-600 font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-xl transition-all ${
                isActive('/') ? 'bg-brand-50 text-brand-600 scale-105' : 'group-hover:bg-slate-100'
              }`}
            >
              <Home className="h-4 w-4" />
            </div>
            <span className="text-[11px] tracking-tight mt-0.5">Home</span>
          </Link>

          {/* Features */}
          <button
            type="button"
            onClick={() => scrollToSection('features')}
            className={`group flex flex-1 flex-col items-center justify-center py-1 transition-all ${
              isActive('/', 'features')
                ? 'text-brand-600 font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-xl transition-all ${
                isActive('/', 'features')
                  ? 'bg-brand-50 text-brand-600 scale-105'
                  : 'group-hover:bg-slate-100'
              }`}
            >
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-[11px] tracking-tight mt-0.5">Features</span>
          </button>

          {/* How It Works */}
          <button
            type="button"
            onClick={() => scrollToSection('how-it-works')}
            className={`group flex flex-1 flex-col items-center justify-center py-1 transition-all ${
              isActive('/', 'how-it-works')
                ? 'text-brand-600 font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-xl transition-all ${
                isActive('/', 'how-it-works')
                  ? 'bg-brand-50 text-brand-600 scale-105'
                  : 'group-hover:bg-slate-100'
              }`}
            >
              <Compass className="h-4 w-4" />
            </div>
            <span className="text-[11px] tracking-tight mt-0.5">How It Works</span>
          </button>

          {/* Dashboard */}
          <Link
            to="/dashboard"
            className={`group flex flex-1 flex-col items-center justify-center py-1 transition-all ${
              location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/workspace')
                ? 'text-brand-600 font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-xl transition-all ${
                location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/workspace')
                  ? 'bg-brand-50 text-brand-600 scale-105'
                  : 'group-hover:bg-slate-100'
              }`}
            >
              <LayoutDashboard className="h-4 w-4" />
            </div>
            <span className="text-[11px] tracking-tight mt-0.5">Dashboard</span>
          </Link>

          {/* Profile / Settings */}
          <button
            type="button"
            onClick={() => setIsSettingsOpen(true)}
            className="group flex flex-1 flex-col items-center justify-center py-1 text-slate-500 hover:text-slate-800 transition-all"
            title="Student Profile & Settings"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-xl group-hover:bg-slate-100 transition-all">
              <User className="h-4 w-4 text-slate-600 group-hover:text-brand-600" />
            </div>
            <span className="text-[11px] tracking-tight mt-0.5 max-w-[64px] truncate">
              {profile?.full_name ? profile.full_name.split(' ')[0] : 'Profile'}
            </span>
          </button>
        </div>
      </nav>

      {/* Profile Settings Modal */}
      <ProfileSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onProfileUpdated={setProfile}
      />
    </>
  );
};

