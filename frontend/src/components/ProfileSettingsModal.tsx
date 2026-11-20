import React, { useState, useEffect } from 'react';
import { X, Trash2, Check, ShieldCheck, AlertCircle, Info, Smartphone } from 'lucide-react';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';

interface ProfileSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileUpdated?: (profile: StudentProfile | null) => void;
  initialTab?: 'profile' | 'settings';
}

export const ProfileSettingsModal: React.FC<ProfileSettingsModalProps> = ({
  isOpen,
  onClose,
  onProfileUpdated,
  initialTab = 'profile',
}) => {
  const [activeTab, setActiveTab] = useState<'profile' | 'settings'>(initialTab);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [enrollmentNumber, setEnrollmentNumber] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [studentId, setStudentId] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      loadData();
    }
  }, [isOpen, initialTab]);

  const loadData = async () => {
    const p = await profileStorage.getProfile();
    setProfile(p);
    if (p) {
      setFullName(p.full_name);
      setEnrollmentNumber(p.enrollment_number);
      setRollNumber(p.roll_number || '');
      setStudentId(p.student_id || '');
    }
    setIsSaved(false);
    setError(null);
  };

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanName = fullName.trim();
    const cleanEnr = enrollmentNumber.trim();

    if (!cleanName || !cleanEnr) {
      setError('Full Name and Enrollment Number are required.');
      return;
    }

    try {
      const updated = await profileStorage.saveProfile({
        full_name: cleanName,
        enrollment_number: cleanEnr,
        roll_number: rollNumber.trim() || null,
        student_id: studentId.trim() || null,
      });

      setProfile(updated);
      setIsSaved(true);
      if (onProfileUpdated) onProfileUpdated(updated);
      setTimeout(() => setIsSaved(false), 2000);
    } catch (err: any) {
      setError(err?.message || 'Failed to update student profile.');
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Delete your student profile from this device?')) {
      await profileStorage.deleteProfile();
      setProfile(null);
      setFullName('');
      setEnrollmentNumber('');
      setRollNumber('');
      setStudentId('');
      if (onProfileUpdated) onProfileUpdated(null);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-sm rounded-2xl bg-white shadow-2xl border border-slate-100 overflow-hidden">
        {/* Header Tabs */}
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
            <button
              type="button"
              onClick={() => setActiveTab('profile')}
              className={`px-3 py-1 rounded-md transition ${
                activeTab === 'profile' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Profile
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('settings')}
              className={`px-3 py-1 rounded-md transition ${
                activeTab === 'settings' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Settings
            </button>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-md transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 flex items-center gap-2 text-xs text-rose-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isSaved && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-2.5 flex items-center gap-2 text-xs text-emerald-800">
              <Check className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>Profile saved successfully</span>
            </div>
          )}

          {activeTab === 'profile' ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Neel Vyas"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Enrollment Number</label>
                <input
                  type="text"
                  required
                  value={enrollmentNumber}
                  onChange={(e) => setEnrollmentNumber(e.target.value)}
                  placeholder="e.g. 92400120560"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Roll Number</label>
                  <input
                    type="text"
                    value={rollNumber}
                    onChange={(e) => setRollNumber(e.target.value)}
                    placeholder="Optional"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Student ID</label>
                  <input
                    type="text"
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    placeholder="Optional"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Offline Privacy Card */}
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-xs text-emerald-900">
                <div className="font-semibold flex items-center gap-1.5 mb-1">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  100% Offline & Private
                </div>
                <p className="text-[11px] text-emerald-800 leading-relaxed">
                  All profiles, footer detection, and PDF personalizations execute entirely on this device. No files or personal data are ever uploaded to cloud servers.
                </p>
              </div>

              {/* App Details Card */}
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-xs text-slate-700 space-y-2">
                <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                  <Smartphone className="h-4 w-4 text-indigo-600" />
                  About DocMorph
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-200/60">
                  <span>Version</span>
                  <span className="font-mono font-medium text-slate-700">1.0.0 (Offline)</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Engine</span>
                  <span className="font-medium text-slate-700">Native PDFBox & ML Kit</span>
                </div>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-100">
            {profile && activeTab === 'profile' ? (
              <button
                type="button"
                onClick={handleDelete}
                className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 p-1.5 rounded-lg hover:bg-rose-50 transition"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition"
              >
                Close
              </button>
              {activeTab === 'profile' && (
                <button
                  type="submit"
                  className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
                >
                  Save
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
