import React, { useState } from 'react';
import { UserCheck, Sparkles, Shield, AlertCircle } from 'lucide-react';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';

interface ProfileSetupModalProps {
  isOpen: boolean;
  onComplete: (profile: StudentProfile) => void;
  canDismiss?: boolean;
  onDismiss?: () => void;
}

export const ProfileSetupModal: React.FC<ProfileSetupModalProps> = ({
  isOpen,
  onComplete,
  canDismiss = false,
  onDismiss,
}) => {
  const [fullName, setFullName] = useState('');
  const [enrollmentNumber, setEnrollmentNumber] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [studentId, setStudentId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanName = fullName.trim();
    const cleanEnr = enrollmentNumber.trim();

    if (!cleanName) {
      setError('Please enter your full name as it appears on academic practicals.');
      return;
    }

    if (!cleanEnr) {
      setError('Please enter your enrollment or registration number.');
      return;
    }

    setIsSaving(true);
    try {
      const saved = await profileStorage.saveProfile({
        full_name: cleanName,
        enrollment_number: cleanEnr,
        roll_number: rollNumber.trim() || null,
        student_id: studentId.trim() || null,
      });
      onComplete(saved);
    } catch (err: any) {
      setError(err?.message || 'Failed to save student profile on device.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-slate-100 overflow-hidden">
        {/* Header gradient banner */}
        <div className="bg-gradient-to-r from-brand-600 via-indigo-600 to-indigo-700 px-6 py-5 text-white">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20 backdrop-blur-md shadow-inner text-white">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">One-Time Student Setup</h2>
              <p className="text-xs text-indigo-100">Set up once. Every practical personalized automatically.</p>
            </div>
          </div>
        </div>

        {/* Content & Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="rounded-xl bg-brand-50/70 border border-brand-100/80 p-3.5 flex items-start gap-3 text-xs text-brand-900">
            <Shield className="h-4 w-4 text-brand-600 mt-0.5 shrink-0" />
            <div>
              <span className="font-semibold">Privacy First:</span> No account or password required. Your details are saved securely on this device and applied to documents you select.
            </div>
          </div>

          {error && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 p-3 flex items-center gap-2.5 text-xs text-rose-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Full Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Neel Vyas"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Enrollment Number <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={enrollmentNumber}
                onChange={(e) => setEnrollmentNumber(e.target.value)}
                placeholder="e.g. 92400120560"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Roll Number <span className="text-slate-400">(Optional)</span>
                </label>
                <input
                  type="text"
                  value={rollNumber}
                  onChange={(e) => setRollNumber(e.target.value)}
                  placeholder="e.g. 42"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Student ID <span className="text-slate-400">(Optional)</span>
                </label>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  placeholder="e.g. CE-2026-042"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 transition-all"
                />
              </div>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            {canDismiss && onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Skip for now
              </button>
            )}
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-semibold text-white shadow-md shadow-brand-500/20 hover:bg-brand-700 active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <UserCheck className="h-4 w-4" />
              {isSaving ? 'Saving Profile...' : 'Save & Continue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

