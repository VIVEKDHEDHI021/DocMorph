import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import {
  DocumentItem,
  DocumentDetectionResponse,
  JobDetail,
  ProfileMatchResult,
  StudentProfile,
} from '../types';
import { PdfViewer } from '../components/PdfViewer';
import { DetectionFieldCard } from '../components/DetectionFieldCard';
import { NativeService } from '../services/nativeService';
import { profileStorage } from '../services/profileStorage';

interface ParsedIdentity {
  name: string;
  identifier: string;
}

function parseCombinedIdentity(text: string): ParsedIdentity {
  const trimmed = text.trim();
  if (!trimmed) return { name: '', identifier: '' };

  const parenMatch = trimmed.match(/^(.+?)\s*[\(\[]\s*([A-Za-z0-9\-_/]+)\s*[\)\]]$/);
  if (parenMatch) return { name: parenMatch[1].trim(), identifier: parenMatch[2].trim() };

  const invParenMatch = trimmed.match(/^[\(\[]\s*([A-Za-z0-9\-_/]+)\s*[\)\]]\s*(.+)$/);
  if (invParenMatch) return { name: invParenMatch[2].trim(), identifier: invParenMatch[1].trim() };

  const invDelim = trimmed.match(/^([A-Za-z0-9\-_/]+)\s*[\-–—|,/]\s*([A-Za-z\s.\'\-]+)$/);
  if (invDelim && /^\d{4,}$/.test(invDelim[1].trim())) {
    return { name: invDelim[2].trim(), identifier: invDelim[1].trim() };
  }

  const standardDelim = trimmed.match(/^([A-Za-z\s.\'\-]+?)\s*[\-–—|,/]\s*([A-Za-z0-9\-_/]+)$/);
  if (standardDelim) {
    return { name: standardDelim[1].trim(), identifier: standardDelim[2].trim() };
  }

  const spaceDigitsMatch = trimmed.match(/^([A-Za-z\s.\'\-]+?)\s+(\d{6,18})$/);
  if (spaceDigitsMatch) return { name: spaceDigitsMatch[1].trim(), identifier: spaceDigitsMatch[2].trim() };

  if (/^\d{6,18}$/.test(trimmed)) {
    return { name: '', identifier: trimmed };
  }

  return { name: trimmed, identifier: '' };
}

export const WorkspacePage: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Active step (1: Preview, 2: Detection & Review, 3: Personalize, 4: Result & Verification)
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [replacementValues, setReplacementValues] = useState<Record<string, string>>({});
  const [combinedValue, setCombinedValue] = useState<string>('');
  const [activePreviewTab, setActivePreviewTab] = useState<'original' | 'personalized'>('personalized');
  const [processingStage, setProcessingStage] = useState<number>(0);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);

  // Profile Auto-Personalization & Native Download state
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [, setMatchResult] = useState<ProfileMatchResult | null>(null);
  const [savedLocalUri, setSavedLocalUri] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccessNotice, setDownloadSuccessNotice] = useState<string | null>(null);
  const [viewerPageInfo, setViewerPageInfo] = useState<{ current: number; total: number }>({ current: 1, total: 1 });

  // 1. Fetch Document Details
  const {
    data: document,
    isLoading: docLoading,
    error: docError,
    refetch: refetchDoc,
  } = useQuery<DocumentItem>({
    queryKey: ['document', documentId],
    queryFn: () => api.documents.getDetail(documentId!),
    enabled: !!documentId,
  });

  // 2. Fetch Detections
  const {
    data: detectionData,
    refetch: refetchDetections,
  } = useQuery<DocumentDetectionResponse>({
    queryKey: ['detections', documentId],
    queryFn: () => api.detections.getDetections(documentId!),
    retry: false,
    enabled: !!documentId && !!document,
  });

  // 3. Fetch latest result / job if already completed
  const {
    data: latestResult,
    refetch: refetchResult,
  } = useQuery<JobDetail>({
    queryKey: ['result', documentId],
    queryFn: () => api.personalization.getLatestResult(documentId!),
    retry: false,
    enabled: !!documentId && !!document && (document.has_personalized_output || document.status === 'completed'),
  });

  // Derived field collections
  const fields = detectionData?.fields || [];
  const confirmedFields = fields.filter(
    (f) => f.review_status === 'confirmed' || f.review_status === 'corrected'
  );

  const nameField = confirmedFields.find((f) => f.field_type === 'student_name');
  const idField = confirmedFields.find((f) =>
    ['enrollment_number', 'roll_number', 'student_id'].includes(f.field_type)
  );
  const isCombinedIdentity = !!(nameField && idField);
  const otherConfirmedFields = confirmedFields.filter(
    (f) => f.field_id !== nameField?.field_id && f.field_id !== idField?.field_id
  );

  const nameOriginal = nameField ? (nameField.original_value || nameField.suggested_value) : '';
  const idOriginal = idField ? (idField.original_value || idField.suggested_value) : '';
  const combinedOriginal = idOriginal ? `${nameOriginal} (${idOriginal})`.trim() : nameOriginal;
  const namePages = Array.isArray(nameField?.pages) ? nameField.pages : [];
  const idPages = Array.isArray(idField?.pages) ? idField.pages : [];
  const combinedPages = Array.from(new Set([...namePages, ...idPages])).sort(
    (a: number, b: number) => a - b
  );

  // Auto-advance step if completed
  useEffect(() => {
    if (latestResult && latestResult.status === 'completed') {
      setCurrentStep(4);
      setActivePreviewTab('personalized');
    } else if (detectionData && detectionData.fields.length > 0) {
      if (currentStep === 1) {
        setCurrentStep(2);
      }
    }
  }, [detectionData, latestResult]);

  // Sync combined input with initial values if available
  useEffect(() => {
    if (isCombinedIdentity && nameField && idField) {
      const profileId = profile?.student_id || profile?.enrollment_number || profile?.roll_number || '';
      const nameVal = replacementValues[nameField.field_id] || profile?.full_name || '';
      const idVal = replacementValues[idField.field_id] || profileId;
      if (!combinedValue && (nameVal || idVal)) {
        setCombinedValue(idVal ? `${nameVal} (${idVal})`.trim() : nameVal);
      }
    }
  }, [currentStep, isCombinedIdentity, nameField?.field_id, idField?.field_id, replacementValues, profile, combinedValue]);

  // Load saved student profile and listen to profile changes
  useEffect(() => {
    profileStorage.getProfile().then(setProfile);
    const unsubscribe = profileStorage.onProfileChange(setProfile);
    return () => unsubscribe();
  }, []);

  // Profile match and pre-populate replacement values (never prompt user repeatedly for ID)
  useEffect(() => {
    if (profile && detectionData && detectionData.fields.length > 0) {
      const profileId = profile.student_id || profile.enrollment_number || profile.roll_number || '';
      const profileRoll = profile.roll_number || profile.enrollment_number || profile.student_id || '';
      const profileEnroll = profile.enrollment_number || profile.student_id || profile.roll_number || '';

      setReplacementValues((prev) => {
        const updated = { ...prev };
        detectionData.fields.forEach((f) => {
          if (!updated[f.field_id] || updated[f.field_id].trim() === '') {
            if (f.field_type === 'student_name' && profile.full_name) {
              updated[f.field_id] = profile.full_name;
            } else if (f.field_type === 'enrollment_number' && profileEnroll) {
              updated[f.field_id] = profileEnroll;
            } else if (f.field_type === 'roll_number' && profileRoll) {
              updated[f.field_id] = profileRoll;
            } else if (f.field_type === 'student_id' && profileId) {
              updated[f.field_id] = profileId;
            }
          }
        });
        return updated;
      });

      if (documentId) {
        api.personalization
          .matchProfile(documentId, profile)
          .then((res) => setMatchResult(res))
          .catch((e) => console.warn('Profile match error:', e));
      }
    }
  }, [documentId, profile, detectionData]);

  // Mutations
  const analyzeMutation = useMutation({
    mutationFn: () => api.detections.analyze(documentId!),
    onSuccess: (data) => {
      queryClient.setQueryData(['detections', documentId], data);
      refetchDoc();
      setCurrentStep(2);
    },
    onError: (err: any) => {
      alert(`Detection analysis failed: ${err.message}`);
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (fieldId: string) => api.detections.confirmField(documentId!, fieldId),
    onSuccess: () => {
      refetchDetections();
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (fieldId: string) => api.detections.rejectField(documentId!, fieldId),
    onSuccess: () => {
      refetchDetections();
    },
  });

  const correctMutation = useMutation({
    mutationFn: ({
      fieldId,
      correctedValue,
      fieldType,
    }: {
      fieldId: string;
      correctedValue: string;
      fieldType?: string;
    }) =>
      api.detections.reviewField(documentId!, fieldId, {
        review_status: 'corrected',
        corrected_value: correctedValue,
        field_type: fieldType,
      }),
    onSuccess: () => {
      refetchDetections();
    },
  });

  // Bulk Confirm All
  const handleConfirmAll = async () => {
    if (!detectionData || !documentId) return;
    const pending = detectionData.fields.filter(
      (f) => f.review_status === 'pending' || f.review_status === 'corrected'
    );
    for (const f of pending) {
      if (f.review_status === 'pending') {
        await api.detections.confirmField(documentId, f.field_id);
      }
    }
    refetchDetections();
  };

  // Personalization execution
  const handleStartPersonalization = async () => {
    if (!documentId) return;
    const confirmed = confirmedFields;

    if (confirmed.length === 0) {
      alert('Please confirm or correct at least one detected field before personalizing.');
      return;
    }

    for (const field of confirmed) {
      const val = replacementValues[field.field_id];
      if (!val || !val.trim()) {
        if (
          isCombinedIdentity &&
          (field.field_id === nameField?.field_id || field.field_id === idField?.field_id)
        ) {
          alert('Please enter both your Student Name and Enrollment Number in the combined field.');
        } else {
          alert(`Please provide a replacement value for "${field.field_type}".`);
        }
        return;
      }
    }

    const payloadReplacements = confirmed.map((f) => ({
      field_id: f.field_id,
      field_type: f.field_type,
      new_value: replacementValues[f.field_id].trim(),
    }));

    setIsProcessing(true);
    setProcessingError(null);
    setProcessingStage(1);

    try {
      await new Promise((res) => setTimeout(res, 350));
      setProcessingStage(2);

      const jobDetail = await api.personalization.personalize(documentId, payloadReplacements);

      setProcessingStage(3);
      await new Promise((res) => setTimeout(res, 350));

      queryClient.setQueryData(['result', documentId], jobDetail);
      refetchDoc();
      refetchResult();
      setIsProcessing(false);
      setCurrentStep(4);
      setActivePreviewTab('personalized');
    } catch (err: any) {
      setIsProcessing(false);
      setProcessingError(err.message || 'Personalization execution failed.');
    }
  };

  // Native & Web PDF Download / Open / Share
  const downloadAndGetUri = async (): Promise<string> => {
    if (!documentId || !document) throw new Error('Document not ready.');
    if (savedLocalUri) return savedLocalUri;

    setIsDownloading(true);
    try {
      const isPersonalized = document.has_personalized_output || activePreviewTab === 'personalized' || currentStep === 4;
      const blob = await api.documents.getPdfBlob(documentId, isPersonalized);
      const outName = isPersonalized
        ? `DocMorph_Personalized_${document.original_filename}`
        : document.original_filename;
      const uri = await NativeService.savePdfLocally(blob, outName);
      setSavedLocalUri(uri);
      setDownloadSuccessNotice(`Saved as ${outName}`);
      return uri;
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownload = async () => {
    if (!documentId || !document) return;
    setIsDownloading(true);
    try {
      const isPersonalized = document.has_personalized_output || activePreviewTab === 'personalized' || currentStep === 4;
      const outName = isPersonalized
        ? `DocMorph_Personalized_${document.original_filename}`
        : document.original_filename;
      if (NativeService.isNative()) {
        const res = await api.personalization.exportPdf(documentId, outName);
        setDownloadSuccessNotice(`Saved to Downloads: ${outName}`);
        setSavedLocalUri(res.exportPath);
        return;
      }
      await downloadAndGetUri();
    } catch (err: any) {
      alert(`Download error: ${err.message}`);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleOpen = async () => {
    if (!documentId) return;
    try {
      if (NativeService.isNative()) {
        await api.personalization.openPdf(documentId, 'personalized');
        return;
      }
      const uri = await downloadAndGetUri();
      await NativeService.openPdf(uri);
    } catch (err: any) {
      alert(`Open error: ${err.message}`);
    }
  };

  const handleShare = async () => {
    if (!documentId) return;
    try {
      if (NativeService.isNative()) {
        await api.personalization.sharePdf(documentId, 'personalized');
        return;
      }
      const uri = await downloadAndGetUri();
      const outName = `DocMorph_Personalized_${document?.original_filename || 'document.pdf'}`;
      await NativeService.sharePdf(uri, outName);
    } catch (err: any) {
      alert(`Share error: ${err.message}`);
    }
  };

  const handleCombinedChange = (val: string) => {
    setCombinedValue(val);
    const parsed = parseCombinedIdentity(val);
    const updated = { ...replacementValues };
    if (nameField) updated[nameField.field_id] = parsed.name;
    if (idField) updated[idField.field_id] = parsed.identifier;
    setReplacementValues(updated);
  };

  const handleSubNameChange = (val: string) => {
    if (!nameField) return;
    const updated = { ...replacementValues, [nameField.field_id]: val };
    setReplacementValues(updated);
    const idVal = idField ? (replacementValues[idField.field_id] || '') : '';
    setCombinedValue(idVal ? `${val} (${idVal})` : val);
  };

  const handleSubIdChange = (val: string) => {
    if (!idField) return;
    const updated = { ...replacementValues, [idField.field_id]: val };
    setReplacementValues(updated);
    const nameVal = nameField ? (replacementValues[nameField.field_id] || '') : '';
    setCombinedValue(nameVal ? `${nameVal} (${val})` : `(${val})`);
  };

  if (!documentId) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-on-surface-variant font-body-md">Document ID is missing.</p>
      </div>
    );
  }

  if (docLoading) {
    return (
      <div className="flex h-[calc(100vh-10rem)] flex-col items-center justify-center gap-3">
        <span className="material-symbols-outlined text-[40px] text-primary animate-spin">progress_activity</span>
        <p className="font-label-md text-label-md text-on-surface font-semibold">Opening document workspace...</p>
      </div>
    );
  }

  if (docError || !document) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center px-4">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-error-container text-error mb-3">
          <span className="material-symbols-outlined text-[28px]">error</span>
        </div>
        <h2 className="font-headline-sm text-headline-sm text-on-surface font-bold">Document Not Found</h2>
        <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
          The requested document could not be loaded from storage.
        </p>
        <button
          onClick={() => navigate('/')}
          className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 font-label-md text-label-md text-on-primary shadow-sm hover:opacity-90"
        >
          <span className="material-symbols-outlined text-[18px]">arrow_back</span>
          Back to Documents
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col w-full bg-surface min-h-screen">
      {/* 1. STICKY TOP HEADER — Never overlaps or collides with content on any device */}
      <header className="sticky top-0 z-40 w-full pt-safe bg-surface/95 backdrop-blur-xl border-b border-surface-container-high/80 shadow-xs">
        <div className="h-14 px-3 sm:px-4 flex items-center justify-between gap-2 max-w-xl mx-auto">
          <div className="flex items-center gap-1.5 min-w-0">
            <button
              onClick={() => navigate('/')}
              className="w-9 h-9 flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container active:bg-surface-container-high transition-colors shrink-0"
              title="Back"
            >
              <span className="material-symbols-outlined text-[20px]">arrow_back_ios_new</span>
            </button>
            <div className="flex flex-col min-w-0">
              <h1 className="font-label-lg text-label-lg text-on-surface truncate font-bold max-w-[190px] xs:max-w-xs sm:max-w-md">
                {document.original_filename}
              </h1>
              <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
                <span className="font-semibold text-primary">
                  {currentStep === 1
                    ? '1. Preview'
                    : currentStep === 2
                    ? `2. Review (${fields.length})`
                    : currentStep === 3
                    ? '3. Personalizing'
                    : '4. Export'}
                </span>
                <span>•</span>
                <span>Page {viewerPageInfo.current}/{viewerPageInfo.total || document.page_count}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {document.has_personalized_output && (
              <span className="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-sm text-label-sm font-semibold">
                Personalized
              </span>
            )}
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="w-8 h-8 rounded-full bg-surface-container hover:bg-surface-container-high text-primary flex items-center justify-center transition-colors active:scale-95 disabled:opacity-50"
              title="Download PDF"
            >
              {isDownloading ? (
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
              ) : (
                <span className="material-symbols-outlined text-[18px]">download</span>
              )}
            </button>
            <button
              onClick={() => navigate('/')}
              className="w-8 h-8 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface flex items-center justify-center transition-colors active:scale-95"
              title="Home"
            >
              <span className="material-symbols-outlined text-[18px]">home</span>
            </button>
          </div>
        </div>

        {/* 4-Step Segmented Bar — Cleanly fits 100% of any mobile screen width */}
        <div className="px-3 sm:px-4 pb-2.5 max-w-xl mx-auto w-full">
          <div className="grid grid-cols-4 gap-1 bg-surface-container-low p-1 rounded-full border border-outline-variant/30 text-center">
            <button
              onClick={() => setCurrentStep(1)}
              className={`py-1 rounded-full font-label-sm text-label-sm transition-all ${
                currentStep === 1
                  ? 'bg-primary text-on-primary font-bold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              1. Preview
            </button>
            <button
              onClick={() => setCurrentStep(2)}
              disabled={fields.length === 0}
              className={`py-1 rounded-full font-label-sm text-label-sm transition-all disabled:opacity-40 ${
                currentStep === 2
                  ? 'bg-primary text-on-primary font-bold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              2. Review
            </button>
            <button
              onClick={() => setCurrentStep(3)}
              disabled={confirmedFields.length === 0}
              className={`py-1 rounded-full font-label-sm text-label-sm transition-all disabled:opacity-40 ${
                currentStep === 3
                  ? 'bg-primary text-on-primary font-bold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              3. Apply
            </button>
            <button
              onClick={() => setCurrentStep(4)}
              disabled={!document.has_personalized_output && !latestResult}
              className={`py-1 rounded-full font-label-sm text-label-sm transition-all disabled:opacity-40 ${
                currentStep === 4
                  ? 'bg-primary text-on-primary font-bold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              4. Export
            </button>
          </div>
        </div>
      </header>

      {/* 2. MAIN SCROLLABLE BODY — Perfectly centered and sized for mobile and all devices */}
      <main className="flex-1 flex flex-col w-full max-w-xl mx-auto px-3 sm:px-4 pt-3 pb-32">
        {/* STEP 1: PREVIEW */}
        {currentStep === 1 && (
          <div className="space-y-3 w-full">
            {/* Document Info Callout */}
            <div className="bg-surface-container-low rounded-xl p-3 shadow-xs border border-outline-variant/40 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-primary-container text-on-primary flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-[18px]">description</span>
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-label-md text-label-md text-on-surface font-bold truncate">
                      {document.original_filename}
                    </span>
                    <span className="bg-primary/10 text-primary font-label-sm text-label-sm px-1.5 py-0.2 rounded font-medium">
                      PDF
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    {document.page_count} Pages • {(document.file_size / 1024).toFixed(1)} KB • 100% Offline
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="h-7 px-2.5 rounded-full bg-primary/10 hover:bg-primary hover:text-on-primary text-primary font-label-sm text-label-sm font-semibold flex items-center gap-1 transition-all active:scale-95"
                  title="Download PDF"
                >
                  <span className="material-symbols-outlined text-[15px]">download</span>
                  <span>Download</span>
                </button>
                <span className="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-sm text-label-sm font-semibold shrink-0">
                  {fields.length > 0 ? `${fields.length} Found` : 'Ready'}
                </span>
              </div>
            </div>

            <PdfViewer
              documentId={documentId}
              title={document.original_filename}
              onPageChange={(curr, total) => setViewerPageInfo({ current: curr, total })}
              onSmartSelectResult={(result) => {
                if (result.footerStatus === 'FOOTER_CONFIRMED' && result.candidates.length > 0) {
                  refetchDetections();
                }
              }}
            />
          </div>
        )}

        {/* STEP 2: DETECTION & REVIEW (Without the redundant auto-personalize section) */}
        {currentStep === 2 && (
          <div className="space-y-3 w-full">
            {/* UNIFIED STUDENT IDENTITY FOOTER CARD */}
            {isCombinedIdentity && (
              <div className="bg-surface-container-lowest rounded-xl p-3.5 shadow-sm border border-outline-variant/60 w-full">
                {/* Header row with responsive wrap protection */}
                <div className="flex items-center justify-between pb-2 border-b border-surface-container-high/60 mb-2.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="material-symbols-outlined text-primary text-[20px] shrink-0">badge</span>
                    <h3 className="font-label-lg text-label-lg text-on-surface font-bold truncate">
                      Unified Student Identity Footer
                    </h3>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {combinedPages.length > 0 && (
                      <span className="px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-semibold">
                        {combinedPages.length} {combinedPages.length === 1 ? 'Page' : 'Pages'}
                      </span>
                    )}
                    <span className="px-2 py-0.5 rounded bg-primary-fixed text-primary font-label-sm text-label-sm font-bold">
                      PAIRED
                    </span>
                  </div>
                </div>

                {combinedPages.length > 0 && (
                  <div className="text-[11px] text-on-surface-variant mb-2.5">
                    Found on pages: <span className="font-semibold text-on-surface">{combinedPages.join(', ')}</span>
                  </div>
                )}

                <div className="space-y-2.5">
                  <div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant block uppercase font-bold">
                      Original Document Value
                    </span>
                    <div className="mt-1 px-3 py-2 rounded-lg bg-surface-container-low font-mono text-xs sm:text-sm text-on-surface font-medium break-all border border-outline-variant/30">
                      {combinedOriginal || 'Not found'}
                    </div>
                  </div>

                  <div>
                    <span className="font-label-sm text-label-sm text-primary block uppercase font-bold">
                      Replacement Value
                    </span>
                    <input
                      type="text"
                      value={combinedValue}
                      onChange={(e) => handleCombinedChange(e.target.value)}
                      placeholder={
                        profile
                          ? `${profile.full_name} (${profile.enrollment_number || profile.student_id || profile.roll_number || ''})`
                          : 'e.g. Vivek Dhedhi (92400120571)'
                      }
                      className="mt-1 w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-outline-variant focus:border-primary focus:outline-none font-medium text-xs sm:text-sm text-on-surface"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    <div>
                      <span className="font-label-sm text-label-sm text-on-surface-variant block">Candidate Name</span>
                      <input
                        type="text"
                        value={nameField ? replacementValues[nameField.field_id] || '' : ''}
                        onChange={(e) => handleSubNameChange(e.target.value)}
                        placeholder={profile?.full_name || 'Candidate Name'}
                        className="mt-1 w-full px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/60 font-body-sm text-body-sm text-on-surface focus:bg-surface-container-lowest focus:border-primary focus:outline-none"
                      />
                    </div>
                    <div>
                      <span className="font-label-sm text-label-sm text-on-surface-variant block">Enrollment / Roll ID</span>
                      <input
                        type="text"
                        value={idField ? replacementValues[idField.field_id] || '' : ''}
                        onChange={(e) => handleSubIdChange(e.target.value)}
                        placeholder={
                          profile?.enrollment_number || profile?.student_id || profile?.roll_number || 'Enrollment / Roll Number'
                        }
                        className="mt-1 w-full px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/60 font-body-sm text-body-sm text-on-surface focus:bg-surface-container-lowest focus:border-primary focus:outline-none"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Other Confirmed Fields */}
            {otherConfirmedFields.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-label-sm text-label-sm text-on-surface-variant uppercase font-bold">Additional Fields</h4>
                {otherConfirmedFields.map((f) => {
                  const fallbackNewVal =
                    f.field_type === 'student_name'
                      ? profile?.full_name
                      : profile?.student_id || profile?.enrollment_number || profile?.roll_number;

                  return (
                    <div key={f.field_id} className="bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/60">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-label-sm text-label-sm uppercase font-bold text-on-surface">{f.field_type}</span>
                        <span className="font-body-sm text-body-sm text-outline">Orig: {f.original_value || f.suggested_value}</span>
                      </div>
                      <input
                        type="text"
                        value={replacementValues[f.field_id] || ''}
                        onChange={(e) =>
                          setReplacementValues({ ...replacementValues, [f.field_id]: e.target.value })
                        }
                        placeholder={fallbackNewVal ? `New value: ${fallbackNewVal}` : `Enter new ${f.field_type}`}
                        className="w-full px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant focus:bg-surface-container-lowest focus:border-primary focus:outline-none text-xs sm:text-sm font-medium text-on-surface"
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {/* All Detected Fields List */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">Detected Credential Records</h3>
                <button
                  onClick={handleConfirmAll}
                  className="font-label-sm text-label-sm text-primary hover:underline font-semibold"
                >
                  Confirm All Pending
                </button>
              </div>

              {fields.map((field) => (
                <DetectionFieldCard
                  key={field.field_id}
                  field={field}
                  onConfirm={(id) => confirmMutation.mutate(id)}
                  onReject={(id) => rejectMutation.mutate(id)}
                  onCorrect={(id, val, type) =>
                    correctMutation.mutate({ fieldId: id, correctedValue: val, fieldType: type })
                  }
                />
              ))}
            </div>
          </div>
        )}

        {/* STEP 3: PERSONALIZATION PROGRESS */}
        {currentStep === 3 && (
          <div className="bg-surface-container-lowest rounded-xl p-6 shadow-sm border border-outline-variant/60 text-center max-w-md mx-auto my-6 w-full">
            <span className="material-symbols-outlined text-[42px] text-primary animate-spin mb-2">sync</span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">Personalizing Document</h3>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-1 mb-4">
              Redacting original streams and injecting verified credentials across all pages.
            </p>

            <div className="space-y-2 text-left">
              <div className="flex items-center gap-2.5 p-2 rounded-lg bg-surface-container-low">
                <span className={`material-symbols-outlined text-[18px] ${processingStage >= 1 ? 'text-secondary' : 'text-outline'}`}>
                  {processingStage >= 1 ? 'check_circle' : 'radio_button_unchecked'}
                </span>
                <span className="font-label-sm text-label-sm text-on-surface">1. Analyzing Typography & Baseline</span>
              </div>
              <div className="flex items-center gap-2.5 p-2 rounded-lg bg-surface-container-low">
                <span className={`material-symbols-outlined text-[18px] ${processingStage >= 2 ? 'text-secondary' : 'text-outline'}`}>
                  {processingStage >= 2 ? 'check_circle' : 'radio_button_unchecked'}
                </span>
                <span className="font-label-sm text-label-sm text-on-surface">2. Redacting Content Streams & Form XObjects</span>
              </div>
              <div className="flex items-center gap-2.5 p-2 rounded-lg bg-surface-container-low">
                <span className={`material-symbols-outlined text-[18px] ${processingStage >= 3 ? 'text-secondary' : 'text-outline'}`}>
                  {processingStage >= 3 ? 'check_circle' : 'radio_button_unchecked'}
                </span>
                <span className="font-label-sm text-label-sm text-on-surface">3. Performing Page-by-Page Output Audit</span>
              </div>
            </div>

            {processingError && (
              <div className="mt-3 p-2.5 rounded-lg bg-error-container text-on-error-container font-body-sm text-body-sm">
                {processingError}
              </div>
            )}
          </div>
        )}

        {/* STEP 4: RESULT & EXPORT */}
        {currentStep === 4 && (
          <div className="space-y-3 w-full">
            {/* Toggle Original vs Personalized */}
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="bg-surface-container p-0.5 rounded-full flex items-center shadow-xs">
                <button
                  onClick={() => setActivePreviewTab('personalized')}
                  className={`px-3.5 py-1 rounded-full font-label-sm text-label-sm font-semibold transition-all ${
                    activePreviewTab === 'personalized'
                      ? 'bg-primary text-on-primary shadow-xs'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Personalized PDF
                </button>
                <button
                  onClick={() => setActivePreviewTab('original')}
                  className={`px-3.5 py-1 rounded-full font-label-sm text-label-sm font-semibold transition-all ${
                    activePreviewTab === 'original'
                      ? 'bg-primary text-on-primary shadow-xs'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Original PDF
                </button>
              </div>
            </div>

            <PdfViewer
              documentId={documentId}
              isPersonalized={activePreviewTab === 'personalized'}
              title={activePreviewTab === 'personalized' ? 'Personalized Document' : 'Original Document'}
              onPageChange={(curr, total) => setViewerPageInfo({ current: curr, total })}
            />

            {/* Quick Export Action Bar */}
            <div className="grid grid-cols-3 gap-2 pt-2">
              <button
                onClick={handleOpen}
                className="h-11 rounded-xl bg-surface-container-lowest border border-outline-variant text-on-surface font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-xs hover:border-primary active:scale-[0.98] transition-all"
              >
                <span className="material-symbols-outlined text-[18px] text-primary">visibility</span>
                Open
              </button>
              <button
                onClick={handleShare}
                className="h-11 rounded-xl bg-surface-container-lowest border border-outline-variant text-on-surface font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-xs hover:border-primary active:scale-[0.98] transition-all"
              >
                <span className="material-symbols-outlined text-[18px] text-secondary">share</span>
                Share
              </button>
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="h-11 rounded-xl bg-gradient-to-r from-primary to-secondary text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-xs active:scale-[0.98] transition-all disabled:opacity-50"
              >
                {isDownloading ? (
                  <span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined text-[18px]">download</span>
                )}
                {isDownloading ? 'Downloading...' : 'Download'}
              </button>
            </div>

            {downloadSuccessNotice && (
              <div className="p-2.5 rounded-lg bg-surface-container text-on-surface text-center font-body-sm text-body-sm">
                {downloadSuccessNotice}
              </div>
            )}
          </div>
        )}
      </main>

      {/* 3. FIXED BOTTOM ACTION BAR — Clean, perfectly fitted on all mobile screens */}
      <aside className="fixed bottom-0 inset-x-0 z-40 pb-safe bg-surface/95 backdrop-blur-xl border-t border-surface-container-high/80 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]">
        <div className="px-3 sm:px-4 py-2.5 flex items-center justify-between gap-3 max-w-xl mx-auto w-full">
          {/* Secondary Action */}
          <button
            onClick={() => {
              if (currentStep > 1) setCurrentStep((prev) => prev - 1);
              else navigate('/');
            }}
            className="px-5 h-11 rounded-full bg-surface-container text-on-surface font-label-md text-label-md flex items-center justify-center active:bg-surface-container-high transition-colors shrink-0"
          >
            {currentStep > 1 ? 'Back' : 'Close'}
          </button>

          {/* Primary Action Button */}
          {currentStep === 1 && (
            <button
              onClick={() => {
                if (fields.length > 0) setCurrentStep(2);
                else analyzeMutation.mutate();
              }}
              disabled={analyzeMutation.isPending}
              className="flex-1 h-11 rounded-full bg-gradient-to-r from-primary to-secondary text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-sm active:scale-[0.98] transition-transform disabled:opacity-50"
            >
              <span>{fields.length > 0 ? `Review Fields (${fields.length})` : 'Analyze Document'}</span>
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </button>
          )}

          {currentStep === 2 && (
            <button
              onClick={handleStartPersonalization}
              disabled={confirmedFields.length === 0 || isProcessing}
              className="flex-1 h-11 rounded-full bg-gradient-to-r from-primary to-secondary text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-sm active:scale-[0.98] transition-transform disabled:opacity-50"
            >
              <span>Personalize Document</span>
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </button>
          )}

          {currentStep === 3 && (
            <button
              disabled
              className="flex-1 h-11 rounded-full bg-primary-container text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5 opacity-70"
            >
              <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
              <span>Processing...</span>
            </button>
          )}

          {currentStep === 4 && (
            <div className="flex-1 flex items-center gap-2">
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex-1 h-11 rounded-full bg-gradient-to-r from-primary to-secondary text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5 shadow-sm active:scale-[0.98] transition-transform disabled:opacity-50"
              >
                {isDownloading ? (
                  <span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined text-[18px]">download</span>
                )}
                <span>{isDownloading ? 'Downloading...' : 'Download PDF'}</span>
              </button>
              <button
                onClick={handleShare}
                className="h-11 px-4 rounded-full bg-surface-container text-on-surface font-label-md text-label-md flex items-center justify-center gap-1.5 active:bg-surface-container-high transition-colors shrink-0"
                title="Share PDF"
              >
                <span className="material-symbols-outlined text-[18px] text-secondary">share</span>
                <span className="text-xs font-semibold">Share</span>
              </button>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
};
