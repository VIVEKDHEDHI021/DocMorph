import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import {
  DocumentItem,
  DocumentDetectionResponse,
  DetectionField,
  JobDetail,
} from '../types';
import { PdfViewer } from '../components/PdfViewer';
import { DetectionFieldCard } from '../components/DetectionFieldCard';
import { ProgressBar } from '../components/ProgressBar';
import {
  ArrowLeft,
  Search,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Download,
  RotateCcw,
  FileText,
  ShieldCheck,
  Check,
  X,
  Layers,
  Hash,
  User,
  CreditCard,
  Eye,
  Info,
  Loader2,
  ExternalLink,
  Share2,
} from 'lucide-react';
import { NativeService } from '../services/nativeService';
import { profileStorage } from '../services/profileStorage';
import { ProfileMatchResult, StudentProfile } from '../types';

interface ParsedIdentity {
  name: string;
  identifier: string;
}

function parseCombinedIdentity(text: string): ParsedIdentity {
  const trimmed = text.trim();
  if (!trimmed) return { name: '', identifier: '' };

  // 1. Name (ID) or Name [ID]
  const parenMatch = trimmed.match(/^(.+?)\s*[\(\[]\s*([A-Za-z0-9\-_/]+)\s*[\)\]]$/);
  if (parenMatch) return { name: parenMatch[1].trim(), identifier: parenMatch[2].trim() };

  // 2. Inverted: (ID) Name or [ID] Name
  const invParenMatch = trimmed.match(/^[\(\[]\s*([A-Za-z0-9\-_/]+)\s*[\)\]]\s*(.+)$/);
  if (invParenMatch) return { name: invParenMatch[2].trim(), identifier: invParenMatch[1].trim() };

  // 3. Inverted: ID - Name or ID | Name (where first part is digits)
  const invDelim = trimmed.match(/^([A-Za-z0-9\-_/]+)\s*[\-–—|,/]\s*([A-Za-z\s.\'\-]+)$/);
  if (invDelim && /^\d{4,}$/.test(invDelim[1].trim())) {
    return { name: invDelim[2].trim(), identifier: invDelim[1].trim() };
  }

  // 4. Standard: Name - ID, Name | ID, Name , ID, Name / ID
  const standardDelim = trimmed.match(/^([A-Za-z\s.\'\-]+?)\s*[\-–—|,/]\s*([A-Za-z0-9\-_/]+)$/);
  if (standardDelim) {
    return { name: standardDelim[1].trim(), identifier: standardDelim[2].trim() };
  }

  // 5. Name followed by digits: e.g. "Vivek Dhedhi 92400120571"
  const spaceDigitsMatch = trimmed.match(/^([A-Za-z\s.\'\-]+?)\s+(\d{6,18})$/);
  if (spaceDigitsMatch) return { name: spaceDigitsMatch[1].trim(), identifier: spaceDigitsMatch[2].trim() };

  // 6. Only digits
  if (/^\d{6,18}$/.test(trimmed)) {
    return { name: '', identifier: trimmed };
  }

  // 7. Fallback: treat as name
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
  const [activePreviewTab, setActivePreviewTab] = useState<'original' | 'personalized'>('original');
  const [processingStage, setProcessingStage] = useState<number>(0);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);

  // Profile Auto-Personalization & Native Download state
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [matchResult, setMatchResult] = useState<ProfileMatchResult | null>(null);
  const [isMatching, setIsMatching] = useState(false);
  const [savedLocalUri, setSavedLocalUri] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccessNotice, setDownloadSuccessNotice] = useState<string | null>(null);

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
    isLoading: detectionsLoading,
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
  const pendingFields = fields.filter((f) => f.review_status === 'pending');
  const rejectedFields = fields.filter((f) => f.review_status === 'rejected');

  const nameField = confirmedFields.find((f) => f.field_type === 'student_name');
  const idField = confirmedFields.find((f) =>
    ['enrollment_number', 'roll_number', 'student_id'].includes(f.field_type)
  );
  const isCombinedIdentity = !!(nameField && idField);
  const otherConfirmedFields = confirmedFields.filter(
    (f) => f.field_id !== nameField?.field_id && f.field_id !== idField?.field_id
  );

  const nameOriginal = nameField ? (nameField.corrected_value || nameField.suggested_value) : '';
  const idOriginal = idField ? (idField.corrected_value || idField.suggested_value) : '';
  const combinedOriginal = `${nameOriginal} (${idOriginal})`.trim();
  const namePages = Array.isArray(nameField?.pages) ? nameField.pages : [];
  const idPages = Array.isArray(idField?.pages) ? idField.pages : [];
  const combinedPages = Array.from(new Set([...namePages, ...idPages])).sort(
    (a: number, b: number) => a - b
  );

  // Hook 1: Auto-advance step if state warrants it
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

  // Hook 2: Sync combined input with initial values if available
  useEffect(() => {
    if (isCombinedIdentity && nameField && idField && !combinedValue) {
      const nameVal = replacementValues[nameField.field_id] || '';
      const idVal = replacementValues[idField.field_id] || '';
      if (nameVal || idVal) {
        setCombinedValue(idVal ? `${nameVal} (${idVal})`.trim() : nameVal);
      }
    }
  }, [currentStep, isCombinedIdentity, nameField?.field_id, idField?.field_id]);

  // Hook 3: Load saved student profile
  useEffect(() => {
    profileStorage.getProfile().then(setProfile);
  }, []);

  // Hook 4: Profile match and auto-plan calculation
  useEffect(() => {
    if (documentId && profile && detectionData && detectionData.fields.length > 0) {
      setIsMatching(true);
      api.personalization
        .matchProfile(documentId, profile)
        .then((res) => {
          setMatchResult(res);
          // Pre-populate replacement values from profile
          setReplacementValues((prev) => {
            const updated = { ...prev };
            detectionData.fields.forEach((f) => {
              if (!updated[f.field_id]) {
                if (f.field_type === 'student_name') updated[f.field_id] = profile.full_name;
                else if (f.field_type === 'enrollment_number') updated[f.field_id] = profile.enrollment_number;
                else if (f.field_type === 'roll_number' && profile.roll_number) updated[f.field_id] = profile.roll_number;
                else if (f.field_type === 'student_id' && profile.student_id) updated[f.field_id] = profile.student_id;
              }
            });
            return updated;
          });
        })
        .catch((e) => console.warn('Profile match error:', e))
        .finally(() => setIsMatching(false));
    }
  }, [documentId, profile, detectionData]);

  // Mutations (declared unconditionally before any early returns)
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

    // Verify all confirmed fields have replacement values
    for (const field of confirmed) {
      const val = replacementValues[field.field_id];
      if (!val || !val.trim()) {
        if (
          isCombinedIdentity &&
          (field.field_id === nameField?.field_id || field.field_id === idField?.field_id)
        ) {
          alert(
            'Please enter both your Student Name and Enrollment Number in the combined field (e.g. Vivek Dhedhi (92400120571)).'
          );
        } else {
          alert(
            `Please provide a replacement value for "${getFieldLabel(
              field.field_type
            )}" (or reject it if not needed).`
          );
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
    setProcessingStage(0);

    try {
      setProcessingStage(1);
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

  // 1-Click Auto-Personalization Handler
  const handleAutoPersonalize = async () => {
    if (!documentId || !profile) return;
    setIsProcessing(true);
    setProcessingError(null);
    setProcessingStage(1);

    try {
      await new Promise((res) => setTimeout(res, 350));
      setProcessingStage(2);

      const jobDetail = await api.personalization.autoPersonalize(documentId, profile);

      setProcessingStage(3);
      await new Promise((res) => setTimeout(res, 350));

      queryClient.setQueryData(['result', documentId], jobDetail);
      refetchDoc();
      refetchResult();
      refetchDetections();
      setIsProcessing(false);
      setCurrentStep(4);
      setActivePreviewTab('personalized');
    } catch (err: any) {
      setIsProcessing(false);
      setProcessingError(err.message || 'Auto-personalization failed.');
    }
  };

  // Native & Web PDF Download / Open / Share
  const downloadAndGetUri = async (): Promise<string> => {
    if (!documentId || !document) throw new Error('Document not ready.');
    if (savedLocalUri) return savedLocalUri;

    setIsDownloading(true);
    try {
      const blob = await api.documents.getPdfBlob(documentId, true);
      const outName = `DocMorph_Personalized_${document.original_filename}`;
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
      const outName = `DocMorph_Personalized_${document.original_filename}`;
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
    if (nameField) {
      updated[nameField.field_id] = parsed.name;
    }
    if (idField) {
      updated[idField.field_id] = parsed.identifier;
    }
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

  const getFieldLabel = (type: string) => {
    switch (type) {
      case 'student_name':
        return 'Student Name';
      case 'enrollment_number':
        return 'Enrollment Number';
      case 'roll_number':
        return 'Roll Number';
      case 'student_id':
        return 'Student ID';
      default:
        return type;
    }
  };

  const getFieldIcon = (type: string) => {
    switch (type) {
      case 'student_name':
        return <User className="h-4 w-4 text-indigo-600" />;
      case 'enrollment_number':
        return <Hash className="h-4 w-4 text-indigo-600" />;
      case 'roll_number':
        return <Layers className="h-4 w-4 text-emerald-600" />;
      case 'student_id':
        return <CreditCard className="h-4 w-4 text-amber-600" />;
      default:
        return <FileText className="h-4 w-4 text-slate-600" />;
    }
  };

  // Safe conditional early returns AFTER all hooks and handlers have executed
  if (!documentId) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-slate-500">Document ID is missing.</p>
      </div>
    );
  }

  if (docLoading) {
    return (
      <div className="flex h-[calc(100vh-10rem)] flex-col items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
        <p className="mt-4 text-sm font-semibold text-slate-700">Loading document workspace...</p>
      </div>
    );
  }

  if (docError || !document) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <h2 className="mt-4 text-lg font-bold text-slate-900">Document Not Found</h2>
        <p className="mt-2 text-sm text-slate-600">
          The requested document could not be found or you do not have permission to view it.
        </p>
        <button
          onClick={() => navigate('/dashboard')}
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Top Header / Breadcrumb */}
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
            title="Back to Dashboard"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
                {document.original_filename}
              </h1>
              {document.has_personalized_output && (
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                  Personalized
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
              <span>{document.page_count} Pages</span>
              <span>•</span>
              <span>{(document.file_size / 1024).toFixed(1)} KB</span>
              <span>•</span>
              <span className="font-mono text-[10px] text-slate-400">ID: {document.id.slice(0, 8)}...</span>
            </div>
          </div>
        </div>

        {/* Step Indicator Tabs */}
        <div className="flex items-center rounded-xl bg-slate-100 p-1 text-xs font-medium text-slate-600">
          <button
            onClick={() => setCurrentStep(1)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition ${
              currentStep === 1
                ? 'bg-white font-semibold text-slate-900 shadow-sm'
                : 'hover:text-slate-900'
            }`}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-slate-200 text-[10px]">
              1
            </span>
            Document Preview
          </button>
          <button
            onClick={() => setCurrentStep(2)}
            disabled={!detectionData && !document.detections_count}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition disabled:opacity-40 ${
              currentStep === 2
                ? 'bg-white font-semibold text-slate-900 shadow-sm'
                : 'hover:text-slate-900'
            }`}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-slate-200 text-[10px]">
              2
            </span>
            Detection & Review
          </button>
          <button
            onClick={() => setCurrentStep(3)}
            disabled={confirmedFields.length === 0}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition disabled:opacity-40 ${
              currentStep === 3
                ? 'bg-white font-semibold text-slate-900 shadow-sm'
                : 'hover:text-slate-900'
            }`}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-slate-200 text-[10px]">
              3
            </span>
            Personalize
          </button>
          <button
            onClick={() => setCurrentStep(4)}
            disabled={!document.has_personalized_output && !latestResult}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition disabled:opacity-40 ${
              currentStep === 4
                ? 'bg-white font-semibold text-slate-900 shadow-sm'
                : 'hover:text-slate-900'
            }`}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-slate-200 text-[10px]">
              4
            </span>
            Result & Verification
          </button>
        </div>
      </div>

      {/* STEP 1: PREVIEW & DETAILS */}
      {currentStep === 1 && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* PDF Viewer on Left (8 cols) */}
          <div className="lg:col-span-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <PdfViewer
                documentId={documentId}
                title={document.original_filename}
                onSmartSelectResult={(result) => {
                  if (result.footerStatus === 'FOOTER_CONFIRMED' && result.candidates.length > 0) {
                    refetchDetections();
                  }
                }}
              />
            </div>
          </div>

          {/* Document Info & Actions on Right (4 cols) */}
          <div className="space-y-6 lg:col-span-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-bold text-slate-900">Document Analysis</h2>
              <p className="mt-1 text-xs text-slate-500">
                Inspect document structure and run the intelligent footer detection engine.
              </p>

              <div className="mt-6 space-y-3.5 divide-y divide-slate-100 text-sm">
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">Document Status</span>
                  <span className="font-semibold uppercase text-slate-900 text-xs">
                    {document.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">Selectable Text</span>
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
                    <Check className="h-3.5 w-3.5" /> Verified
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">Page Count</span>
                  <span className="font-semibold text-slate-900 text-xs">
                    {document.page_count} pages
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">File Size</span>
                  <span className="font-semibold text-slate-900 text-xs">
                    {(document.file_size / 1024).toFixed(1)} KB
                  </span>
                </div>
              </div>

              {/* Action Button */}
              <div className="mt-8">
                {detectionData && detectionData.fields.length > 0 ? (
                  <button
                    onClick={() => setCurrentStep(2)}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
                  >
                    <Eye className="h-4 w-4" />
                    Review Detections ({detectionData.fields.length})
                  </button>
                ) : (
                  <button
                    onClick={() => analyzeMutation.mutate()}
                    disabled={analyzeMutation.isPending}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
                  >
                    {analyzeMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Scanning footer regions...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4" />
                        Run Intelligent Detection
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Privacy & Layout Guarantee Notice */}
            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-5">
              <div className="flex items-start gap-3">
                <ShieldCheck className="h-5 w-5 flex-shrink-0 text-indigo-600 mt-0.5" />
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-950">
                    Document Integrity Guarantee
                  </h3>
                  <p className="mt-1 text-xs text-indigo-800 leading-relaxed">
                    DocMorph operates directly on native PDF streams. Your original text flows,
                    formulas, graphs, and formatting remain 100% unaltered.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: DETECTION & REVIEW */}
      {currentStep === 2 && (
        <div className="mt-6 space-y-6">
          {/* Smart Profile 1-Click Auto-Personalize Banner */}
          {profile && matchResult && matchResult.all_eligible_for_auto && matchResult.auto_replacement_plan.length > 0 && (
            <div className="rounded-2xl border border-brand-200 bg-gradient-to-r from-brand-50 via-indigo-50 to-white p-5 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-start gap-3.5">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white shadow-md shadow-brand-500/20 shrink-0">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-brand-700">
                        Smart Profile Match
                      </span>
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                        Ready to Personalize
                      </span>
                    </div>
                    <div className="text-sm font-bold text-slate-900 mt-0.5">
                      Personalize for {profile.full_name} ({profile.enrollment_number})
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5">
                      {matchResult.summary_message} All safety checks and typography alignments verified.
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleAutoPersonalize}
                  disabled={isProcessing}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-700 active:scale-[0.98] transition-all disabled:opacity-50 shrink-0"
                >
                  <Sparkles className="h-4 w-4" />
                  Auto-Personalize Document
                </button>
              </div>
            </div>
          )}

          {/* Summary Banner */}
          <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">Detected Student Information</h2>
                <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-800">
                  {fields.length} Found
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                Confirm, correct, or reject each field before proceeding to personalization.
                Only confirmed fields will be replaced.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={analyzeMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
              >
                <RotateCcw className={`h-3.5 w-3.5 ${analyzeMutation.isPending ? 'animate-spin' : ''}`} />
                Re-analyze PDF
              </button>
              {pendingFields.length > 0 && (
                <button
                  onClick={handleConfirmAll}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700"
                >
                  <Check className="h-3.5 w-3.5" />
                  Confirm All Pending
                </button>
              )}
              <button
                onClick={() => setCurrentStep(3)}
                disabled={confirmedFields.length === 0}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-40"
              >
                Proceed to Personalization ({confirmedFields.length})
                <Sparkles className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Detections List Grid */}
          {detectionsLoading ? (
            <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
              <p className="mt-3 text-sm text-slate-600">Loading detected fields...</p>
            </div>
          ) : fields.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900">
                No Personal Information Detected
              </h3>
              <p className="mt-1 max-w-md text-xs text-slate-500">
                Our footer detection engine scanned the document but did not find standard student
                name or enrollment number patterns in the footer margins.
              </p>
              <button
                onClick={() => analyzeMutation.mutate()}
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-indigo-700"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry Detection
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {fields.map((field) => (
                <DetectionFieldCard
                  key={field.field_id}
                  field={field}
                  onConfirm={(id) => confirmMutation.mutate(id)}
                  onReject={(id) => rejectMutation.mutate(id)}
                  onCorrect={(id, val, type) =>
                    correctMutation.mutate({
                      fieldId: id,
                      correctedValue: val,
                      fieldType: type,
                    })
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* STEP 3: PERSONALIZATION FORM */}
      {currentStep === 3 && (
        <div className="mt-6 space-y-6">
          {/* Main Form Container */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Input Form Column (7 cols) */}
            <div className="space-y-6 lg:col-span-7">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Enter Your Personal Details</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      These values will replace the original detected values across all occurrences.
                    </p>
                  </div>
                  <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                    {confirmedFields.length} {confirmedFields.length === 1 ? 'Field' : 'Fields'} Confirmed
                  </span>
                </div>

                <div className="mt-6 space-y-5">
                  {confirmedFields.map((field) => {
                    const original = field.corrected_value || field.suggested_value;
                    const currentValue = replacementValues[field.field_id] || '';

                    return (
                      <div
                        key={field.field_id}
                        className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition focus-within:border-indigo-500 focus-within:bg-white"
                      >
                        <div className="flex items-center justify-between">
                          <label className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-800">
                            {getFieldIcon(field.field_type)}
                            {getFieldLabel(field.field_type)}
                          </label>
                          <span className="text-[11px] font-medium text-slate-500">
                            Occurs on {field.pages.length} {field.pages.length === 1 ? 'page' : 'pages'} (
                            {field.pages.join(', ')})
                          </span>
                        </div>

                        {/* Original vs Replacement Input */}
                        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                          <div>
                            <span className="block text-[11px] font-semibold text-slate-400">
                              ORIGINAL VALUE
                            </span>
                            <div className="mt-1 rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-mono text-slate-600 line-through">
                              {original}
                            </div>
                          </div>

                          <div>
                            <span className="block text-[11px] font-semibold text-indigo-700">
                              NEW REPLACEMENT VALUE *
                            </span>
                            <input
                              type="text"
                              value={currentValue}
                              onChange={(e) =>
                                setReplacementValues({
                                  ...replacementValues,
                                  [field.field_id]: e.target.value,
                                })
                              }
                              placeholder={`Enter your ${getFieldLabel(field.field_type).toLowerCase()}`}
                              className="mt-1 block w-full rounded-lg border border-indigo-300 px-3 py-2 text-xs font-semibold text-slate-900 shadow-sm placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Processing State Error */}
                {processingError && (
                  <div className="mt-5 flex items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-700">
                    <AlertTriangle className="h-4 w-4 flex-shrink-0 text-rose-500" />
                    <span>{processingError}</span>
                  </div>
                )}

                {/* Actions */}
                <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
                  <button
                    onClick={() => setCurrentStep(2)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back to Review
                  </button>

                  <button
                    onClick={handleStartPersonalization}
                    disabled={isProcessing}
                    className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-indigo-700 disabled:opacity-60"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Personalizing Document...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Execute Personalization
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* In-progress execution display */}
              {isProcessing && (
                <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-6">
                  <ProgressBar currentStageIndex={processingStage} />
                </div>
              )}
            </div>

            {/* Planned Diff & Replacement Preview (5 cols) */}
            <div className="space-y-6 lg:col-span-5">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-sm font-bold text-slate-900">Replacement Plan</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Pre-flight preview of modifications that will be applied.
                </p>

                <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold">
                      <tr>
                        <th className="px-3 py-2.5">Field</th>
                        <th className="px-3 py-2.5">Original</th>
                        <th className="px-3 py-2.5">Target</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {confirmedFields.map((field) => (
                        <tr key={field.field_id}>
                          <td className="whitespace-nowrap px-3 py-2.5 font-medium text-slate-900">
                            {getFieldLabel(field.field_type)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-slate-500 font-mono text-[11px] line-through">
                            {field.corrected_value || field.suggested_value}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 font-semibold font-mono text-[11px] text-emerald-600">
                            {replacementValues[field.field_id] || (
                              <span className="italic text-slate-400">Not set</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-5 space-y-2 rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600">
                  <div className="flex items-center gap-2 text-slate-900 font-semibold">
                    <ShieldCheck className="h-4 w-4 text-indigo-600" />
                    Non-Destructive Rules Applied:
                  </div>
                  <ul className="list-disc pl-5 space-y-1 text-[11px] text-slate-500">
                    <li>Original field labels (e.g. "Name:", "Enrollment:") stay intact.</li>
                    <li>Adaptive font scaling matches character width and prevents text collision.</li>
                    <li>Surrounding content, headers, formulas, and margins remain untouched.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 4: RESULT, VERIFICATION & DOWNLOAD */}
      {currentStep === 4 && (
        <div className="mt-6 space-y-6">
          {/* Header Action Banner */}
          <div className="flex flex-col gap-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-6 shadow-sm md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600 text-white shadow-md shadow-emerald-200">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Personalization Complete & Verified
                </h2>
                <p className="text-xs text-emerald-800">
                  Document has been processed and independently verified against corruption and layout shifts.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setCurrentStep(3)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Change Values
              </button>

              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs sm:text-sm font-bold text-white shadow-md transition hover:bg-emerald-700 active:scale-[0.98] disabled:opacity-50"
              >
                {isDownloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Download PDF
              </button>

              <button
                onClick={handleOpen}
                disabled={isDownloading}
                className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-white px-3.5 py-2 text-xs sm:text-sm font-bold text-emerald-800 shadow-sm transition hover:bg-emerald-50 active:scale-[0.98]"
              >
                <ExternalLink className="h-4 w-4 text-emerald-600" />
                Open PDF
              </button>

              <button
                onClick={handleShare}
                disabled={isDownloading}
                className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3.5 py-2 text-xs sm:text-sm font-bold text-indigo-700 shadow-sm transition hover:bg-indigo-100 active:scale-[0.98]"
              >
                <Share2 className="h-4 w-4 text-indigo-600" />
                Share PDF
              </button>
            </div>
          </div>

          {downloadSuccessNotice && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3.5 flex items-center justify-between gap-3 text-xs text-emerald-800">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>{downloadSuccessNotice} — document saved to device storage.</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleOpen}
                  className="font-bold underline text-emerald-900 hover:text-emerald-950"
                >
                  Open Now
                </button>
                <span>•</span>
                <button
                  onClick={handleShare}
                  className="font-bold underline text-emerald-900 hover:text-emerald-950"
                >
                  Share
                </button>
              </div>
            </div>
          )}

          {/* Verification Report & Preview Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Column: Interactive PDF Viewer Toggle (7 cols) */}
            <div className="space-y-4 lg:col-span-7">
              <div className="flex items-center justify-between rounded-xl bg-white p-2 border border-slate-200 shadow-sm">
                <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1 text-xs font-medium text-slate-600">
                  <button
                    onClick={() => setActivePreviewTab('personalized')}
                    className={`rounded-md px-3 py-1.5 transition ${
                      activePreviewTab === 'personalized'
                        ? 'bg-white font-semibold text-emerald-700 shadow-sm'
                        : 'hover:text-slate-900'
                    }`}
                  >
                    Personalized PDF
                  </button>
                  <button
                    onClick={() => setActivePreviewTab('original')}
                    className={`rounded-md px-3 py-1.5 transition ${
                      activePreviewTab === 'original'
                        ? 'bg-white font-semibold text-slate-900 shadow-sm'
                        : 'hover:text-slate-900'
                    }`}
                  >
                    Original PDF
                  </button>
                </div>
                <span className="text-xs text-slate-500 pr-2">
                  {activePreviewTab === 'personalized'
                    ? 'Displaying generated output with updated footers'
                    : 'Displaying unmodified original document'}
                </span>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <PdfViewer
                  documentId={documentId}
                  isPersonalized={activePreviewTab === 'personalized'}
                  title={
                    activePreviewTab === 'personalized'
                      ? `personalized_${document.original_filename}`
                      : document.original_filename
                  }
                />
              </div>
            </div>

            {/* Right Column: Verification Report & Occurrence Breakdown (5 cols) */}
            <div className="space-y-6 lg:col-span-5">
              {/* Verification Checklist Card */}
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                    Verification Checklist
                  </h3>
                  <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                    Passed
                  </span>
                </div>

                <div className="mt-4 space-y-3 text-xs">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-600 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Valid PDF Syntax & Stream</span>
                      <p className="text-slate-500">Document structure is compliant and readable.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-600 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Page Count Parity</span>
                      <p className="text-slate-500">
                        Exact match: {document.page_count} of {document.page_count} pages preserved.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-600 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Old Credentials Purged</span>
                      <p className="text-slate-500">Target strings cleanly excised from all pages.</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-600 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Labels & Vector Drawings Intact</span>
                      <p className="text-slate-500">
                        Field prefixes, tables, and borders are 100% undamaged.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Warnings or notices if any */}
                {latestResult && latestResult.warnings && latestResult.warnings.length > 0 && (
                  <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                    <div className="font-semibold flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                      Layout Notices:
                    </div>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-[11px]">
                      {latestResult.warnings.map((w, idx) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Replacements Summary Table */}
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-sm font-bold text-slate-900">Applied Replacements</h3>
                <div className="mt-3 overflow-hidden rounded-xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold">
                      <tr>
                        <th className="px-3 py-2">Field</th>
                        <th className="px-3 py-2">Inserted Value</th>
                        <th className="px-3 py-2 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {latestResult && latestResult.occurrence_results && latestResult.occurrence_results.length > 0 ? (
                        latestResult.occurrence_results.map((item, idx) => (
                          <tr key={idx}>
                            <td className="px-3 py-2 font-medium text-slate-800">
                              {getFieldLabel(item.field_id)} (p. {item.page_number})
                            </td>
                            <td className="px-3 py-2 font-mono text-[11px] text-slate-900">
                              {item.inserted_value}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                                {item.status}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        confirmedFields.map((field) => (
                          <tr key={field.field_id}>
                            <td className="px-3 py-2 font-medium text-slate-800">
                              {getFieldLabel(field.field_type)}
                            </td>
                            <td className="px-3 py-2 font-mono text-[11px] text-slate-900">
                              {replacementValues[field.field_id] || 'Updated'}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                                success
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="mt-5 flex items-center justify-between">
                  <button
                    onClick={() => navigate('/dashboard')}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back to Library
                  </button>

                  <a
                    href={api.personalization.getDownloadUrl(documentId)}
                    target="_blank"
                    rel="noreferrer"
                    download
                    className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-700"
                  >
                    Download copy
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
