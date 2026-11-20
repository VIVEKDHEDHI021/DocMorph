import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { DocumentItem, StudentProfile } from '../types';
import { profileStorage } from '../services/profileStorage';
import { NativeService } from '../services/nativeService';
import { ProfileSetupModal } from '../components/ProfileSetupModal';
import { ProfileSettingsModal } from '../components/ProfileSettingsModal';
import { DocumentCard } from '../components/DocumentCard';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragOver, setDragOver] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadToast, setDownloadToast] = useState<string | null>(null);

  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  useEffect(() => {
    api.ensureSession();
    profileStorage.getProfile().then((p) => {
      setProfile(p);
      if (!p) {
        setShowSetupModal(true);
      }
    });

    const unsubscribe = profileStorage.onProfileChange(setProfile);

    // Listen for custom event from floating Iridescent Add PDF button
    const handleGlobalAddPdf = (e: any) => {
      if (e.detail) {
        validateAndUpload(e.detail);
      } else {
        handleSelectPdf();
      }
    };
    window.addEventListener('docmorph:add-pdf', handleGlobalAddPdf);

    return () => {
      unsubscribe();
      window.removeEventListener('docmorph:add-pdf', handleGlobalAddPdf);
    };
  }, []);

  const {
    data: documentsData,
    isLoading,
  } = useQuery({
    queryKey: ['documents', user?.id],
    queryFn: () => api.documents.list(1, 100),
    enabled: !!user?.id,
    refetchInterval: 10000,
  });

  const documents = documentsData?.items || [];

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.documents.upload(file),
    onSuccess: (newDoc) => {
      queryClient.invalidateQueries({ queryKey: ['documents', user?.id] });
      navigate(`/workspace/${newDoc.id}`);
    },
    onError: (err: any) => {
      setUploadError(err.message || 'Failed to upload PDF.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.documents.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', user?.id] });
      setDeletingId(null);
    },
    onError: (err: any) => {
      alert(`Delete failed: ${err.message}`);
      setDeletingId(null);
    },
  });

  const handleSelectPdf = async () => {
    setUploadError(null);
    try {
      const picked = await NativeService.pickPdfFile();
      if (picked && picked.file) {
        validateAndUpload(picked.file);
      }
    } catch (err: any) {
      setUploadError(err.message || 'Failed to select PDF document.');
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    setUploadError(null);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      validateAndUpload(files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndUpload(e.target.files[0]);
    }
  };

  const validateAndUpload = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setUploadError('Only PDF files are supported.');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File size exceeds 50MB limit.');
      return;
    }
    setUploadError(null);
    uploadMutation.mutate(file);
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete "${name}"?`)) {
      setDeletingId(id);
      deleteMutation.mutate(id);
    }
  };

  const handleDownload = async (id: string, name: string) => {
    setDownloadingId(id);
    try {
      const doc = documents.find((d) => d.id === id);
      const isPersonalized = doc?.has_personalized_output || doc?.status === 'completed';
      const cleanName = isPersonalized ? `DocMorph_Personalized_${name}` : name;
      await api.personalization.exportPdf(id, cleanName);
      setDownloadToast(`Saved to Downloads: ${cleanName}`);
      setTimeout(() => setDownloadToast(null), 4000);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredDocs = documents.filter((doc) =>
    doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalCount = documents.length;
  const completedCount = documents.filter((d) => d.status === 'completed' || d.has_personalized_output).length;
  const recentDocs = filteredDocs.slice(0, 5);

  return (
    <div className="w-full max-w-xl mx-auto px-3 sm:px-4 pt-3 pb-36">
      {/* Student Profile & Engine Callout Banner (Matching DESIGN.md) */}
      <div className="mb-3 bg-surface-container-low rounded-xl p-3 shadow-xs relative overflow-hidden">
        <div className="absolute -right-4 -bottom-4 w-28 h-28 bg-gradient-to-br from-primary-fixed to-secondary-fixed opacity-40 rounded-full blur-xl pointer-events-none" />
        <div className="flex items-center justify-between gap-2 relative z-10">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-primary-container text-on-primary flex items-center justify-center shrink-0 shadow-xs">
              <span className="material-symbols-outlined text-[18px]">school</span>
            </div>
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <h2 className="text-xs sm:text-sm text-on-surface truncate font-semibold">
                  {profile ? profile.full_name : 'Student Profile Not Configured'}
                </h2>
                {profile?.enrollment_number && (
                  <span className="bg-primary/10 text-primary text-[10px] px-1.5 py-0.2 rounded font-medium shrink-0">
                    {profile.enrollment_number}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-on-surface-variant truncate">
                {profile
                  ? `Roll: ${profile.roll_number || 'N/A'} • ID: ${profile.student_id || profile.enrollment_number}`
                  : 'Auto-match and personalize assignment footers.'}
              </p>
            </div>
          </div>

          <button
            onClick={() => (profile ? setShowSettingsModal(true) : setShowSetupModal(true))}
            className="inline-flex items-center px-2.5 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant text-xs font-semibold shrink-0 hover:opacity-90 transition-opacity"
          >
            {profile ? 'Edit' : 'Set Up'}
          </button>
        </div>
      </div>

      {/* Main Drag & Drop / File Select Zone */}
      <div className="mb-3">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileInputChange}
          className="hidden"
        />

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleFileDrop}
          onClick={handleSelectPdf}
          className={`cursor-pointer rounded-xl border border-dashed p-3 text-center transition-all bg-surface-container-lowest/90 active:scale-[0.99] ${
            dragOver
              ? 'border-primary bg-primary-fixed/30'
              : 'border-outline-variant hover:border-primary hover:bg-surface-container-low/40'
          }`}
        >
          {uploadMutation.isPending ? (
            <div className="flex items-center justify-center gap-2 py-2">
              <span className="material-symbols-outlined text-[20px] text-primary animate-spin">sync</span>
              <p className="text-xs text-on-surface font-semibold">Importing PDF locally...</p>
            </div>
          ) : (
            <div className="flex items-center justify-center gap-3 py-1">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 shadow-xs">
                <span className="material-symbols-outlined text-[20px]">upload_file</span>
              </div>
              <div className="text-left min-w-0">
                <span className="inline-block rounded-full bg-gradient-to-r from-primary to-secondary text-on-primary text-xs font-semibold px-3 py-1 shadow-sm">
                  Select PDF Document
                </span>
                <p className="text-[10px] text-outline mt-0.5 truncate">Tap to pick PDF • Offline & up to 50MB</p>
              </div>
            </div>
          )}
        </div>

        {uploadError && (
          <div className="mt-2 flex items-center gap-1.5 rounded-xl bg-error-container p-2 text-on-error-container border border-error/20">
            <span className="material-symbols-outlined text-[16px] text-error shrink-0">error</span>
            <span className="text-xs">{uploadError}</span>
          </div>
        )}
      </div>

      {downloadToast && (
        <div className="mb-3 flex items-center gap-2 rounded-xl bg-secondary-fixed/90 p-2.5 text-on-secondary-fixed-variant border border-secondary/20 shadow-sm animate-fade-in">
          <span className="material-symbols-outlined text-[18px] text-secondary">check_circle</span>
          <span className="text-xs font-semibold flex-1 truncate">{downloadToast}</span>
        </div>
      )}

      {/* Header & Actions */}
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-baseline gap-1.5">
            <h2 className="text-sm sm:text-base text-on-surface font-bold tracking-tight">Recent Documents</h2>
            {totalCount > 0 && (
              <span className="text-[11px] text-on-surface-variant truncate">
                (showing {recentDocs.length} of {totalCount})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {totalCount > 5 && (
            <button
              type="button"
              onClick={() => navigate('/history')}
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-0.5 px-2 py-1 rounded-lg hover:bg-primary/5 transition-colors"
            >
              <span>See All ({totalCount})</span>
              <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
            </button>
          )}
        </div>
      </div>

      {/* Document List (Max 5 on Home Screen) */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center rounded-xl bg-surface-container-lowest py-8 border border-outline-variant/50">
          <span className="material-symbols-outlined text-[24px] text-primary animate-spin">progress_activity</span>
        </div>
      ) : recentDocs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl bg-surface-container-lowest py-8 text-center border border-outline-variant/50">
          <span className="material-symbols-outlined text-[32px] text-outline-variant">description</span>
          <p className="mt-1.5 text-xs text-on-surface font-semibold">
            {searchQuery ? 'No matching documents' : 'No documents yet'}
          </p>
          <p className="text-[11px] text-outline mt-0.5">Tap the + button to add a PDF</p>
        </div>
      ) : (
        <div className="space-y-2">
          {recentDocs.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onOpen={(id) => navigate(`/workspace/${id}`)}
              onDelete={handleDelete}
              onDownload={handleDownload}
              isDeleting={deletingId === doc.id}
              isDownloading={downloadingId === doc.id}
            />
          ))}

          {totalCount > 5 && (
            <div className="pt-2">
              <button
                type="button"
                onClick={() => navigate('/history')}
                className="w-full py-2.5 px-3 rounded-xl bg-surface-container-low hover:bg-surface-container text-primary font-semibold text-xs flex items-center justify-center gap-1.5 transition-all active:scale-[0.99] border border-outline-variant/50 shadow-xs"
              >
                <span className="material-symbols-outlined text-[17px]">history</span>
                <span>View Full Document History ({totalCount} files)</span>
                <span className="material-symbols-outlined text-[16px]">chevron_right</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Profile Setup Modal */}
      <ProfileSetupModal
        isOpen={showSetupModal}
        canDismiss={true}
        onDismiss={() => setShowSetupModal(false)}
        onComplete={(p) => {
          setProfile(p);
          setShowSetupModal(false);
        }}
      />

      {/* Profile Settings Modal */}
      <ProfileSettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        onProfileUpdated={setProfile}
      />
    </div>
  );
};
