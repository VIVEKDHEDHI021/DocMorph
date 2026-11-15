import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { DocumentItem, DocumentStatus, StudentProfile } from '../types';
import { profileStorage } from '../services/profileStorage';
import { NativeService } from '../services/nativeService';
import { ProfileSetupModal } from '../components/ProfileSetupModal';
import { ProfileSettingsModal } from '../components/ProfileSettingsModal';
import {
  UploadCloud,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  ArrowRight,
  Download,
  RefreshCw,
  Search,
  Sparkles,
  Layers,
  CheckCircle,
  XCircle,
  Loader2,
  User,
  Settings,
  ShieldCheck,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragOver, setDragOver] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Profile management state
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  useEffect(() => {
    // 1. Ensure anonymous session is ready
    api.ensureSession();

    // 2. Check for local student profile
    profileStorage.getProfile().then((p) => {
      setProfile(p);
      if (!p) {
        setShowSetupModal(true);
      }
    });

    const unsubscribe = profileStorage.onProfileChange(setProfile);
    return unsubscribe;
  }, []);

  // Fetch documents strictly scoped to current user id
  const {
    data: documentsData,
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['documents', user?.id],
    queryFn: () => api.documents.list(1, 100),
    enabled: !!user?.id,
    refetchInterval: 10000,
  });

  const documents = documentsData?.items || [];

  // Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.documents.upload(file),
    onSuccess: (newDoc) => {
      queryClient.invalidateQueries({ queryKey: ['documents', user?.id] });
      navigate(`/workspace/${newDoc.id}`);
    },
    onError: (err: any) => {
      setUploadError(err.message || 'Failed to upload document. Please ensure it is a valid PDF.');
    },
  });

  // Delete Mutation
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
    if (file.size > 20 * 1024 * 1024) {
      setUploadError('File size exceeds the 20MB limit.');
      return;
    }
    setUploadError(null);
    uploadMutation.mutate(file);
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      setDeletingId(id);
      deleteMutation.mutate(id);
    }
  };

  // Filtered documents
  const filteredDocs = documents.filter((doc) =>
    doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Statistics
  const totalCount = documents.length;
  const completedCount = documents.filter((d) => d.status === 'completed' || d.has_personalized_output).length;
  const reviewCount = documents.filter((d) => d.status === 'awaiting_review' || d.status === 'uploaded').length;
  const totalPages = documents.reduce((acc, d) => acc + (d.page_count || 0), 0);

  const getStatusBadge = (status: DocumentStatus, hasOutput?: boolean) => {
    if (hasOutput || status === 'completed') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
          <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
          Personalized
        </span>
      );
    }

    switch (status) {
      case 'uploaded':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-600/20">
            <Clock className="h-3.5 w-3.5 text-slate-500" />
            Uploaded
          </span>
        );
      case 'analyzing':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-600/20">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
            Analyzing
          </span>
        );
      case 'awaiting_review':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
            Needs Review
          </span>
        );
      case 'ready_to_personalize':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            Ready
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
            Personalizing
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/20">
            <XCircle className="h-3.5 w-3.5 text-rose-600" />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {status}
          </span>
        );
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Top Banner / Heading */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Document Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Personalize academic practical manuals with safe vector-preserving text replacement.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isRefetching}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            title="Refresh document list"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleSelectPdf}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            <UploadCloud className="h-4 w-4" />
            Select PDF
          </button>
        </div>
      </div>

      {/* Student Profile Persistent Status Banner */}
      <div className="mt-6 rounded-2xl bg-gradient-to-r from-brand-50 via-indigo-50/50 to-white border border-brand-200/70 p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white shadow-md shadow-brand-500/20">
              <User className="h-5 w-5" />
            </div>
            <div>
              {profile ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-wider text-brand-700">Target Student Identity</span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
                      <ShieldCheck className="h-3 w-3" /> Ready
                    </span>
                  </div>
                  <div className="text-sm font-bold text-slate-900">
                    {profile.full_name}{' '}
                    <span className="font-mono font-medium text-slate-600">({profile.enrollment_number})</span>
                    {profile.roll_number && (
                      <span className="text-xs text-slate-500 ml-2">Roll: {profile.roll_number}</span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="text-xs font-medium uppercase tracking-wider text-amber-700">Profile Not Configured</div>
                  <div className="text-sm font-semibold text-slate-900">
                    Set up your name and enrollment number for 1-click automatic personalization.
                  </div>
                </>
              )}
            </div>
          </div>
          <button
            onClick={() => (profile ? setShowSettingsModal(true) : setShowSetupModal(true))}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-brand-700 shadow-sm hover:bg-brand-50 transition-colors"
          >
            <Settings className="h-3.5 w-3.5" />
            {profile ? 'Edit Profile' : 'Set Up Details'}
          </button>
        </div>
      </div>

      {/* On-Device Storage Notice */}
      <div className="mt-6 flex items-start gap-3 rounded-2xl border border-sky-200/80 bg-sky-50/70 p-4 text-xs text-sky-900 shadow-sm">
        <ShieldCheck className="h-5 w-5 flex-shrink-0 text-sky-600 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-semibold">100% Offline & Private:</span> All student profiles and documents are stored exclusively on this device. No data is ever sent to cloud servers. Note: App-private files are removed if the app is uninstalled—use <span className="font-semibold">Export / Save to Downloads</span> in the workspace to save permanent copies to your device.
        </div>
      </div>

      {/* Metric Cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Documents
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <FileText className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">{totalCount}</div>
          <p className="mt-1 text-xs text-slate-500">Across your personal library</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Personalized
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-emerald-700">{completedCount}</div>
          <p className="mt-1 text-xs text-slate-500">Ready for submission</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Awaiting Review
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-amber-700">{reviewCount}</div>
          <p className="mt-1 text-xs text-slate-500">Pending student confirmation</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Pages Processed
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <Layers className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 text-2xl font-bold text-purple-700">{totalPages}</div>
          <p className="mt-1 text-xs text-slate-500">Layouts preserved without Word export</p>
        </div>
      </div>

      {/* Drag & Drop / Native Pick Upload Zone */}
      <div className="mt-8">
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
          className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
            dragOver
              ? 'border-indigo-600 bg-indigo-50/50'
              : 'border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50/50'
          }`}
        >
          {uploadMutation.isPending ? (
            <div className="flex flex-col items-center justify-center py-4">
              <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
              <p className="mt-3 text-sm font-semibold text-slate-900">Uploading and validating PDF...</p>
              <p className="mt-1 text-xs text-slate-500">Checking document integrity and selectable text</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div className="mt-4">
                <span className="font-semibold text-indigo-600 hover:text-indigo-500">
                  Select PDF Document
                </span>{' '}
                <span className="text-slate-600">or drag and drop here</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Native Android file picker supported • Up to 50MB (Lab reports, assignments, practical manuals)
              </p>
            </div>
          )}
        </div>

        {uploadError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-rose-500" />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* Documents Table Section */}
      <div className="mt-10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-bold text-slate-900">Your Documents</h2>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Search className="h-4 w-4 text-slate-400" />
            </div>
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 py-1.5 pl-9 pr-3 text-xs text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
            <p className="mt-3 text-sm text-slate-500">Loading document library...</p>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
              <FileText className="h-6 w-6" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-900">No documents found</h3>
            <p className="mt-1 text-xs text-slate-500">
              {searchQuery ? 'No documents match your search query.' : 'Upload your first academic practical PDF above to begin.'}
            </p>
          </div>
        ) : (
          <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Document
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Pages / Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Uploaded
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {filteredDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                            <FileText className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900 text-sm">{doc.original_filename}</div>
                            <div className="text-[11px] text-slate-400 font-mono">ID: {doc.id.slice(0, 8)}...</div>
                          </div>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-xs text-slate-600">
                        <div>{doc.page_count} pages</div>
                        <div className="text-slate-400">{formatFileSize(doc.file_size)}</div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        {getStatusBadge(doc.status, doc.has_personalized_output)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-xs text-slate-500">
                        {formatDate(doc.created_at)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-xs font-medium">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => navigate(`/workspace/${doc.id}`)}
                            className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
                          >
                            Open Studio
                            <ArrowRight className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(doc.id, doc.original_filename)}
                            disabled={deletingId === doc.id}
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-colors disabled:opacity-50"
                            title="Delete document"
                          >
                            {deletingId === doc.id ? (
                              <Loader2 className="h-4 w-4 animate-spin text-rose-600" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* First-time Profile Setup Modal */}
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
