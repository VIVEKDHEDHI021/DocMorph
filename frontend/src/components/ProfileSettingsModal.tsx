import React, { useState, useEffect } from 'react';
import { X, User, Trash2, Check, Server, ShieldCheck, AlertCircle } from 'lucide-react';
import { profileStorage } from '../services/profileStorage';
import { StudentProfile } from '../types';
import { getApiBaseUrl } from '../services/api';

interface ProfileSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileUpdated?: (profile: StudentProfile | null) => void;
}

export const ProfileSettingsModal: React.FC<ProfileSettingsModalProps> = ({
  isOpen,
  onClose,
  onProfileUpdated,
}) => {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [enrollmentNumber, setEnrollmentNumber] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [studentId, setStudentId] = useState('');
  const [backendUrl, setBackendUrl] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    const p = await profileStorage.getProfile();
    setProfile(p);
    if (p) {
      setFullName(p.full_name);
      setEnrollmentNumber(p.enrollment_number);
      setRollNumber(p.roll_number || '');
      setStudentId(p.student_id || '');
    }
    const storedBackend = localStorage.getItem('docmorph_backend_url') || '';
    setBackendUrl(storedBackend);
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

      // Update backend URL if provided
      if (backendUrl.trim()) {
        localStorage.setItem('docmorph_backend_url', backendUrl.trim().replace(/\/+$/, ''));
      } else {
        localStorage.removeItem('docmorph_backend_url');
      }

      setProfile(updated);
      setIsSaved(true);
      if (onProfileUpdated) onProfileUpdated(updated);
      setTimeout(() => setIsSaved(false), 2500);
    } catch (err: any) {
      setError(err?.message || 'Failed to update student profile.');
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to remove your saved student profile from this device?')) {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 font-semibold">
              <User className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Student Profile & Settings</h2>
              <p className="text-xs text-slate-500">Stored locally on this device</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 p-3 flex items-center gap-2 text-xs text-rose-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isSaved && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 flex items-center gap-2 text-xs text-emerald-800">
              <Check className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>Profile updated successfully!</span>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Neel Vyas"
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-sm text-slate-900 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
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
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-sm text-slate-900 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Roll Number</label>
                <input
                  type="text"
                  value={rollNumber}
                  onChange={(e) => setRollNumber(e.target.value)}
                  placeholder="Optional"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Student ID</label>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  placeholder="Optional"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
              </div>
            </div>

            {/* Backend Server Configuration */}
            <div className="pt-2 border-t border-slate-100">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 mb-1">
                <Server className="h-3.5 w-3.5 text-slate-500" />
                Backend Server URL
              </label>
              <input
                type="text"
                value={backendUrl}
                onChange={(e) => setBackendUrl(e.target.value)}
                placeholder={`Default: ${getApiBaseUrl()}`}
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-xs font-mono text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Leave empty to use automatic host detection (ADB reverse / local loopback).
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-3 flex items-center justify-between">
            {profile ? (
              <button
                type="button"
                onClick={handleDelete}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 p-2 rounded-lg hover:bg-rose-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Delete Profile
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Close
              </button>
              <button
                type="submit"
                className="rounded-xl bg-brand-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-brand-700 active:scale-[0.98] transition-all"
              >
                Save Changes
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

