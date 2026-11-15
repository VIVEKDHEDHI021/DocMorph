import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { FileText, LogOut, User as UserIcon, Sparkles, Settings } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';
import { ProfileSettingsModal } from './ProfileSettingsModal';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    profileStorage.getProfile().then(setProfile);
    const unsubscribe = profileStorage.onProfileChange(setProfile);
    return unsubscribe;
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const isWorkspace = location.pathname.startsWith('/workspace');

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Brand Logo */}
          <Link to="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-90">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 shadow-md shadow-brand-500/20 text-white">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-slate-900">DocMorph</span>
              <span className="hidden sm:inline-block ml-2 text-xs font-medium text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full border border-brand-200/60">
                Personalized
              </span>
            </div>
          </Link>

          {/* Right Action / Profile Controls */}
          <div className="flex items-center gap-2.5">
            {/* Student Profile Quick Access Pill */}
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-slate-50/80 hover:bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors shadow-sm"
              title="Student Profile & Settings"
            >
              <UserIcon className="h-3.5 w-3.5 text-brand-600" />
              <span className="max-w-[120px] truncate">
                {profile?.full_name || 'My Profile'}
              </span>
              <Settings className="h-3 w-3 text-slate-400 ml-0.5" />
            </button>

            {isAuthenticated ? (
              <div className="flex items-center gap-2">
                <Link
                  to="/dashboard"
                  className="hidden sm:flex items-center gap-2 text-xs font-semibold text-slate-700 hover:text-brand-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100"
                >
                  Dashboard
                </Link>
                <button
                  onClick={handleLogout}
                  title="Sign out"
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/dashboard"
                  className="inline-flex items-center justify-center rounded-lg bg-brand-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-brand-700 transition-all"
                >
                  Open Studio
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Settings & Profile Modal */}
      <ProfileSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onProfileUpdated={setProfile}
      />
    </>
  );
};
