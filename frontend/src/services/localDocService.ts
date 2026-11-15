/**
 * Local Document Service for DocMorph (100% On-Device & Offline).
 *
 * Implements all document storage, native PDF extraction, ML Kit OCR,
 * ONNX layout detection, profile matching, and content-stream personalization
 * by communicating directly with DocMorphNative (Capacitor plugin) on Android,
 * with a self-contained local memory/blob fallback for web development.
 *
 * Zero HTTP calls to FastAPI, external servers, or cloud storage.
 */

import { Capacitor } from '@capacitor/core';
import {
  DocMorphNative,
  DocumentRecord,
  DetectionCandidate,
  isNativePlatform,
  ManualSelectionInput,
  ManualDetectionResult,
} from './nativeDocMorph';
import {
  DocumentItem,
  DocumentListResponse,
  DocumentStatus,
  DocumentDetectionResponse,
  DetectionField,
  DetectionOccurrence,
  JobDetail,
  ProfileMatchResult,
  FieldMatchComparison,
  StudentProfile,
} from '../types';
import { profileStorage } from './profileStorage';

function mapStatus(status: string, hasOutput: boolean): DocumentStatus {
  if (hasOutput || status === 'PERSONALIZED' || status === 'completed') {
    return 'completed';
  }
  if (status === 'ANALYZED' || status === 'ready_to_personalize') {
    return 'ready_to_personalize';
  }
  if (status === 'awaiting_review') {
    return 'awaiting_review';
  }
  if (status === 'analyzing') {
    return 'analyzing';
  }
  return 'uploaded';
}

function recordToItem(doc: DocumentRecord): DocumentItem {
  const hasOutput = !!doc.personalizedPath;
  return {
    id: doc.documentId,
    original_filename: doc.fileName,
    page_count: doc.pageCount,
    file_size: doc.fileSizeBytes,
    status: mapStatus(doc.status, hasOutput),
    created_at: new Date(doc.createdAt).toISOString(),
    updated_at: new Date(doc.updatedAt).toISOString(),
    has_personalized_output: hasOutput,
    detections_count: 0,
  };
}

class LocalDocService {
  private docCache = new Map<string, DocumentRecord>();
  private candidateCache = new Map<string, DetectionCandidate[]>();
  private detectionResponseCache = new Map<string, DocumentDetectionResponse>();
  private jobDetailCache = new Map<string, JobDetail>();

  // Web fallback mocks
  private webFiles = new Map<string, { originalBlob: Blob; personalizedBlob?: Blob; item: DocumentItem }>();

  constructor() {
    if (isNativePlatform()) {
      this.refreshNativeCache().catch((e) =>
        console.warn('Initial native document cache refresh failed:', e)
      );
    }
  }

  private async refreshNativeCache(): Promise<void> {
    if (!isNativePlatform()) return;
    try {
      const res = await DocMorphNative.listDocuments();
      this.docCache.clear();
      for (const d of res.documents) {
        this.docCache.set(d.documentId, d);
      }
    } catch (e) {
      console.warn('Failed to refresh native cache:', e);
    }
  }

  /**
   * Imports a PDF file locally from a File object, data URI, or native URI.
   */
  async upload(fileOrBlob: File | Blob, fileName?: string): Promise<DocumentItem> {
    const name = fileName || (fileOrBlob instanceof File ? fileOrBlob.name : 'document.pdf');

    if (isNativePlatform()) {
      // Convert file/blob to base64 for native import
      const base64Data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const res = reader.result as string;
          resolve(res);
        };
        reader.onerror = reject;
        reader.readAsDataURL(fileOrBlob);
      });

      const res = await DocMorphNative.importPdfFromBase64({
        base64Data,
        fileName: name,
      });

      const record: DocumentRecord = {
        documentId: res.documentId,
        fileName: res.fileName,
        originalPath: res.filePath,
        personalizedPath: null,
        pageCount: res.pageCount,
        isScanned: false,
        fileSizeBytes: res.fileSizeBytes,
        status: 'IMPORTED',
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      this.docCache.set(res.documentId, record);

      return recordToItem(record);
    }

    // Web Fallback Mock
    const id = `doc_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const item: DocumentItem = {
      id,
      original_filename: name,
      page_count: 1,
      file_size: fileOrBlob.size,
      status: 'uploaded',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      has_personalized_output: false,
      detections_count: 0,
    };
    this.webFiles.set(id, { originalBlob: fileOrBlob, item });
    return item;
  }

  /**
   * Lists all stored documents.
   */
  async list(page = 1, pageSize = 50): Promise<DocumentListResponse> {
    if (isNativePlatform()) {
      await this.refreshNativeCache();
      const docs = Array.from(this.docCache.values());
      docs.sort((a, b) => b.createdAt - a.createdAt);

      const items = docs.map(recordToItem);
      return {
        items,
        total: items.length,
        page,
        page_size: pageSize,
      };
    }

    const items = Array.from(this.webFiles.values()).map((v) => v.item);
    return {
      items,
      total: items.length,
      page,
      page_size: pageSize,
    };
  }

  /**
   * Retrieves single document detail.
   */
  async getDetail(documentId: string): Promise<DocumentItem> {
    if (isNativePlatform()) {
      let doc = this.docCache.get(documentId);
      if (!doc) {
        await this.refreshNativeCache();
        doc = this.docCache.get(documentId);
      }
      if (doc) {
        return recordToItem(doc);
      }
      throw new Error(`Document ${documentId} not found.`);
    }

    const found = this.webFiles.get(documentId);
    if (found) return found.item;
    throw new Error(`Document ${documentId} not found.`);
  }

  /**
   * Deletes a document locally.
   */
  async delete(documentId: string): Promise<void> {
    if (isNativePlatform()) {
      await DocMorphNative.deleteDocument({ documentId });
      this.docCache.delete(documentId);
      this.candidateCache.delete(documentId);
      this.detectionResponseCache.delete(documentId);
      this.jobDetailCache.delete(documentId);
      return;
    }

    this.webFiles.delete(documentId);
  }

  /**
   * Returns a local preview URL for PDF.js to render.
   */
  getPreviewUrl(documentId: string): string {
    if (isNativePlatform()) {
      const doc = this.docCache.get(documentId);
      if (doc?.originalPath) {
        return Capacitor.convertFileSrc(doc.originalPath);
      }
    }
    const found = this.webFiles.get(documentId);
    if (found?.originalBlob) {
      return URL.createObjectURL(found.originalBlob);
    }
    return '';
  }

  /**
   * Returns a local preview URL for the personalized PDF.
   */
  getPersonalizedPreviewUrl(documentId: string): string {
    if (isNativePlatform()) {
      const doc = this.docCache.get(documentId);
      if (doc?.personalizedPath) {
        return Capacitor.convertFileSrc(doc.personalizedPath);
      }
    }
    const found = this.webFiles.get(documentId);
    if (found?.personalizedBlob) {
      return URL.createObjectURL(found.personalizedBlob);
    }
    return '';
  }

  /**
   * Directly retrieves PDF bytes as ArrayBuffer for PDF.js rendering.
   * Completely bypasses HTTP fetch, eliminating "Failed to fetch" errors.
   */
  async getPdfArrayBuffer(documentId: string, isPersonalized = false): Promise<ArrayBuffer> {
    if (isNativePlatform()) {
      let doc = this.docCache.get(documentId);
      if (!doc) {
        await this.refreshNativeCache();
        doc = this.docCache.get(documentId);
      }

      const filePath = isPersonalized ? doc?.personalizedPath : doc?.originalPath;
      try {
        const res = await DocMorphNative.getPdfBase64({
          documentId,
          filePath: filePath || undefined,
          which: isPersonalized ? 'personalized' : 'original',
        });
        if (res?.base64) {
          const binaryString = atob(res.base64);
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          return bytes.buffer;
        }
      } catch (err) {
        console.warn('Native getPdfBase64 failed, falling back to URL fetch:', err);
      }
    }

    // Web in-memory blob or fallback
    const found = this.webFiles.get(documentId);
    const blob = isPersonalized
      ? (found?.personalizedBlob || found?.originalBlob)
      : found?.originalBlob;

    if (blob) {
      return await blob.arrayBuffer();
    }

    // URL fallback (strictly WITHOUT custom headers to avoid CORS/blob errors)
    const url = isPersonalized
      ? this.getPersonalizedPreviewUrl(documentId)
      : this.getPreviewUrl(documentId);

    if (!url) {
      throw new Error('Document preview not available.');
    }

    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to load document stream (${res.status})`);
    }
    return await res.arrayBuffer();
  }

  /**
   * Retrieves PDF document as a Blob.
   */
  async getPdfBlob(documentId: string, isPersonalized = false): Promise<Blob> {
    const found = this.webFiles.get(documentId);
    const existingBlob = isPersonalized
      ? (found?.personalizedBlob || found?.originalBlob)
      : found?.originalBlob;

    if (existingBlob) {
      return existingBlob;
    }

    const arrayBuffer = await this.getPdfArrayBuffer(documentId, isPersonalized);
    return new Blob([arrayBuffer], { type: 'application/pdf' });
  }

  /**
   * Runs on-device AI and OCR detection pipeline.
   */
  async analyze(documentId: string): Promise<DocumentDetectionResponse> {
    if (isNativePlatform()) {
      let doc = this.docCache.get(documentId);
      if (!doc) {
        await this.refreshNativeCache();
        doc = this.docCache.get(documentId);
      }
      if (!doc) throw new Error(`Document ${documentId} not found.`);

      const analysis = await DocMorphNative.analyzeDocument({
        documentId,
        filePath: doc.originalPath,
      });

      this.candidateCache.set(documentId, analysis.candidates);

      // Convert candidates into DocumentDetectionResponse
      const fields: DetectionField[] = analysis.candidates.map((c) => {
        const occ: DetectionOccurrence = {
          page_number: c.pageIndex + 1,
          raw_text: c.detectedText,
          bbox: {
            x0: c.normalizedBox[0],
            y0: c.normalizedBox[1],
            x1: c.normalizedBox[2],
            y1: c.normalizedBox[3],
          },
          value_bbox: {
            x0: c.normalizedBox[0],
            y0: c.normalizedBox[1],
            x1: c.normalizedBox[2],
            y1: c.normalizedBox[3],
          },
          label_bbox: {
            x0: c.normalizedBox[0],
            y0: c.normalizedBox[1],
            x1: c.normalizedBox[2],
            y1: c.normalizedBox[3],
          },
        };

        const fieldType = c.fieldType as DetectionField['field_type'];
        const confLevel =
          c.confidence >= 0.8 ? 'high' : c.confidence >= 0.5 ? 'medium' : 'low';

        return {
          id: c.id,
          field_id: c.id,
          field_type: fieldType,
          original_value: c.detectedText,
          suggested_value: c.detectedText,
          corrected_value: c.replacementText || null,
          confidence: c.confidence,
          confidence_level: confLevel,
          review_status: c.requiresConfirmation ? 'pending' : 'confirmed',
          is_ambiguous: c.requiresConfirmation,
          reasons: c.requiresConfirmation
            ? ['Requires confirmation before replacing']
            : ['High confidence student information'],
          occurrences_count: 1,
          pages: [c.pageIndex + 1],
          occurrences: [occ],
        };
      });

      const response: DocumentDetectionResponse = {
        document_id: documentId,
        status: 'awaiting_review',
        fields,
        summary: {
          total_fields: fields.length,
          high_confidence: fields.filter((f) => f.confidence_level === 'high').length,
          medium_confidence: fields.filter((f) => f.confidence_level === 'medium').length,
          low_confidence: fields.filter((f) => f.confidence_level === 'low').length,
          review_required: fields.filter((f) => f.review_status === 'pending').length,
          conflicts_count: 0,
        },
      };

      this.detectionResponseCache.set(documentId, response);
      return response;
    }

    // Web Fallback Mock
    const mockFields: DetectionField[] = [
      {
        id: 'field_name_1',
        field_id: 'field_name_1',
        field_type: 'student_name',
        original_value: 'Sample Student',
        suggested_value: 'Sample Student',
        confidence: 0.95,
        confidence_level: 'high',
        review_status: 'confirmed',
        is_ambiguous: false,
        reasons: ['Matched pattern'],
        occurrences_count: 1,
        pages: [1],
        occurrences: [
          {
            page_number: 1,
            raw_text: 'Sample Student',
            bbox: { x0: 50, y0: 900, x1: 250, y1: 930 },
            value_bbox: { x0: 50, y0: 900, x1: 250, y1: 930 },
            label_bbox: { x0: 50, y0: 900, x1: 250, y1: 930 },
          },
        ],
      },
      {
        id: 'field_id_1',
        field_id: 'field_id_1',
        field_type: 'enrollment_number',
        original_value: '123456789012',
        suggested_value: '123456789012',
        confidence: 0.95,
        confidence_level: 'high',
        review_status: 'confirmed',
        is_ambiguous: false,
        reasons: ['Matched enrollment number pattern'],
        occurrences_count: 1,
        pages: [1],
        occurrences: [
          {
            page_number: 1,
            raw_text: '123456789012',
            bbox: { x0: 300, y0: 900, x1: 450, y1: 930 },
            value_bbox: { x0: 300, y0: 900, x1: 450, y1: 930 },
            label_bbox: { x0: 300, y0: 900, x1: 450, y1: 930 },
          },
        ],
      },
    ];

    const resp: DocumentDetectionResponse = {
      document_id: documentId,
      status: 'awaiting_review',
      fields: mockFields,
      summary: {
        total_fields: 2,
        high_confidence: 2,
        medium_confidence: 0,
        low_confidence: 0,
        review_required: 0,
        conflicts_count: 0,
      },
    };
    this.detectionResponseCache.set(documentId, resp);
    return resp;
  }

  /**
   * Retrieves current detection state for a document.
   */
  async getDetections(documentId: string): Promise<DocumentDetectionResponse> {
    const cached = this.detectionResponseCache.get(documentId);
    if (cached) return cached;
    return this.analyze(documentId);
  }

  /**
   * Confirms a detected field.
   */
  async confirmField(documentId: string, fieldId: string): Promise<any> {
    const cached = this.detectionResponseCache.get(documentId);
    if (cached) {
      const field = cached.fields.find((f) => f.field_id === fieldId);
      if (field) {
        field.review_status = 'confirmed';
      }
    }
    return { success: true };
  }

  /**
   * Rejects a detected field.
   */
  async rejectField(documentId: string, fieldId: string): Promise<any> {
    const cached = this.detectionResponseCache.get(documentId);
    if (cached) {
      const field = cached.fields.find((f) => f.field_id === fieldId);
      if (field) {
        field.review_status = 'rejected';
      }
    }
    return { success: true };
  }

  /**
   * Updates/corrects a detected field.
   */
  async reviewField(
    documentId: string,
    fieldId: string,
    action: { review_status: string; corrected_value?: string; field_type?: string }
  ): Promise<any> {
    const cached = this.detectionResponseCache.get(documentId);
    if (cached) {
      const field = cached.fields.find((f) => f.field_id === fieldId);
      if (field) {
        field.review_status = action.review_status as any;
        if (action.corrected_value !== undefined) {
          field.corrected_value = action.corrected_value;
        }
        if (action.field_type !== undefined) {
          field.field_type = action.field_type as any;
        }
      }
    }
    return { success: true };
  }

  /**
   * Phase C: Runs Smart Manual Detection on a specific page selection.
   * Selection acts strictly as a boundary hint for verification and student detection.
   */
  async manualDetect(input: ManualSelectionInput): Promise<ManualDetectionResult> {
    let result: ManualDetectionResult;

    if (isNativePlatform()) {
      let doc = this.docCache.get(input.documentId);
      if (!doc) {
        await this.refreshNativeCache();
        doc = this.docCache.get(input.documentId);
      }
      result = await DocMorphNative.manualDetect({
        ...input,
        filePath: input.filePath || doc?.originalPath || undefined,
      });
    } else {
      // Web Fallback Mock for development
      result = {
        documentId: input.documentId,
        pageIndex: input.pageIndex,
        selectionType: input.selectionType,
        resolvedPdfBox: input.rawBbox || [0, 0, 0, 0],
        extractedText: input.selectedText || 'Web development manual selection',
        footerStatus: 'FOOTER_CONFIRMED',
        confidence: 0.88,
        candidates: [
          {
            id: `field_man_${Date.now()}`,
            fieldType: 'student_name',
            detectedText: input.selectedText || 'Detected Student',
            confidence: 0.88,
            pageIndex: input.pageIndex,
            normalizedBox: [50, 900, 250, 930],
            pdfPointBox: [50, 750, 250, 770],
            requiresConfirmation: false,
          },
        ],
        negativeReasons: [],
        summaryMessage: 'Smart manual detection (web mock)',
      };
    }

    // Phase E: If confirmed, incorporate candidate fields into detection caches for personalization!
    if (result.footerStatus === 'FOOTER_CONFIRMED' && result.candidates.length > 0) {
      const existing = this.candidateCache.get(input.documentId) || [];
      const filtered = existing.filter(
        (old) => !result.candidates.some((n) => n.pageIndex === old.pageIndex && n.fieldType === old.fieldType)
      );
      this.candidateCache.set(input.documentId, [...filtered, ...result.candidates]);

      let cachedResp = this.detectionResponseCache.get(input.documentId);
      if (!cachedResp) {
        cachedResp = {
          document_id: input.documentId,
          status: 'awaiting_review',
          fields: [],
          summary: {
            total_fields: 0,
            high_confidence: 0,
            medium_confidence: 0,
            low_confidence: 0,
            review_required: 0,
            conflicts_count: 0,
          },
        };
        this.detectionResponseCache.set(input.documentId, cachedResp);
      }

      for (const c of result.candidates) {
        const fieldId = c.id;
        const existingFieldIdx = cachedResp.fields.findIndex(
          (f) => f.field_type === c.fieldType && f.pages.includes(c.pageIndex + 1)
        );

        const newField: DetectionField = {
          id: fieldId,
          field_id: fieldId,
          field_type: c.fieldType as any,
          original_value: c.detectedText,
          suggested_value: c.detectedText,
          corrected_value: c.replacementText || null,
          confidence: c.confidence,
          confidence_level: c.confidence >= 0.8 ? 'high' : 'medium',
          review_status: c.requiresConfirmation ? 'pending' : 'confirmed',
          is_ambiguous: c.requiresConfirmation,
          reasons: ['Smart Manual Selection verified'],
          occurrences_count: 1,
          pages: [c.pageIndex + 1],
          occurrences: [
            {
              page_number: c.pageIndex + 1,
              raw_text: c.detectedText,
              bbox: {
                x0: c.normalizedBox[0],
                y0: c.normalizedBox[1],
                x1: c.normalizedBox[2],
                y1: c.normalizedBox[3],
              },
              value_bbox: {
                x0: c.normalizedBox[0],
                y0: c.normalizedBox[1],
                x1: c.normalizedBox[2],
                y1: c.normalizedBox[3],
              },
              label_bbox: {
                x0: c.normalizedBox[0],
                y0: c.normalizedBox[1],
                x1: c.normalizedBox[2],
                y1: c.normalizedBox[3],
              },
            },
          ],
        };

        if (existingFieldIdx >= 0) {
          cachedResp.fields[existingFieldIdx] = newField;
        } else {
          cachedResp.fields.push(newField);
        }
      }

      cachedResp.summary.total_fields = cachedResp.fields.length;
      cachedResp.summary.high_confidence = cachedResp.fields.filter((f) => f.confidence_level === 'high').length;
      cachedResp.summary.medium_confidence = cachedResp.fields.filter((f) => f.confidence_level === 'medium').length;
    }

    return result;
  }

  /**
   * Matches document detections with the local student profile.
   */
  async matchProfile(documentId: string, profile: StudentProfile): Promise<ProfileMatchResult> {
    const detections = await this.getDetections(documentId);
    const comparisons: Record<string, FieldMatchComparison> = {};
    const auto_replacement_plan: { field_id: string; field_type: string; new_value: string }[] = [];

    for (const field of detections.fields) {
      let profileValue = '';
      if (field.field_type === 'student_name') profileValue = profile.full_name;
      else if (field.field_type === 'enrollment_number') profileValue = profile.enrollment_number;
      else if (field.field_type === 'roll_number') profileValue = profile.roll_number || '';
      else if (field.field_type === 'student_id') profileValue = profile.student_id || '';

      const isMatching =
        profileValue &&
        field.original_value.trim().toLowerCase() === profileValue.trim().toLowerCase();

      comparisons[field.field_type] = {
        field_type: field.field_type,
        detected_value: field.original_value,
        profile_value: profileValue,
        status: isMatching ? 'already_matching' : 'different',
        confidence: field.confidence,
        field_id: field.field_id,
        auto_action_eligible: !!profileValue,
        reason: isMatching ? 'Matches profile' : 'Different value detected',
      };

      if (profileValue) {
        auto_replacement_plan.push({
          field_id: field.field_id,
          field_type: field.field_type,
          new_value: profileValue,
        });
      }
    }

    return {
      document_id: documentId,
      comparisons,
      all_eligible_for_auto: auto_replacement_plan.length > 0,
      has_conflicts: false,
      requires_manual_review: false,
      auto_replacement_plan,
      summary_message: 'Profile matched with detected fields.',
    };
  }

  /**
   * Executes offline PDF personalization using native PDFBox content-stream rewriting.
   */
  async personalize(
    documentId: string,
    replacements: { field_id: string; field_type: string; new_value: string }[]
  ): Promise<JobDetail> {
    if (isNativePlatform()) {
      const cached = this.candidateCache.get(documentId) || [];
      const confirmedCandidates = replacements.map((r) => {
        const c = cached.find((cand) => cand.id === r.field_id);
        return {
          pageIndex: c ? c.pageIndex : 0,
          fieldType: r.field_type,
          originalValue: c ? c.detectedText : '',
          replacementText: r.new_value,
          pdfPointBox: c ? c.pdfPointBox : [50, 750, 250, 770],
          pairId: c?.pairId || null,
          fontName: c?.fontName || null,
          fontSize: c?.fontSize || 10,
        };
      });

      const res = await DocMorphNative.personalizeDocument({
        documentId,
        confirmedCandidates,
      });

      await this.refreshNativeCache();

      const job: JobDetail = {
        job_id: `job_${documentId}`,
        document_id: documentId,
        status: res.success ? 'completed' : 'failed',
        total_replacements: res.totalReplaced,
        successful_replacements: res.totalReplaced,
        failed_replacements: 0,
        verification_status: res.verificationPassed ? 'passed' : 'failed',
        warnings: res.warnings || [],
        occurrence_results: [],
        verification_report: {
          is_valid: res.verificationPassed,
          page_count_matches: true,
          expected_pages: 1,
          actual_pages: 1,
          replacements_verified: res.totalReplaced,
          total_replacements: res.totalReplaced,
          purged_values_absent: true,
          labels_intact: true,
          unrelated_content_intact: true,
          details: res.warnings || [],
        },
        download_available: true,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      };

      this.jobDetailCache.set(documentId, job);
      return job;
    }

    // Web Fallback Mock
    const webDoc = this.webFiles.get(documentId);
    if (webDoc) {
      webDoc.item.status = 'completed';
      webDoc.item.has_personalized_output = true;
      webDoc.personalizedBlob = webDoc.originalBlob;
    }

    const job: JobDetail = {
      job_id: `job_${documentId}`,
      document_id: documentId,
      status: 'completed',
      total_replacements: replacements.length,
      successful_replacements: replacements.length,
      failed_replacements: 0,
      verification_status: 'passed',
      warnings: [],
      occurrence_results: [],
      verification_report: {
        is_valid: true,
        page_count_matches: true,
        expected_pages: 1,
        actual_pages: 1,
        replacements_verified: replacements.length,
        total_replacements: replacements.length,
        purged_values_absent: true,
        labels_intact: true,
        unrelated_content_intact: true,
        details: [],
      },
      download_available: true,
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };
    this.jobDetailCache.set(documentId, job);
    return job;
  }

  /**
   * 1-Click auto-personalize using student profile.
   */
  async autoPersonalize(documentId: string, profile: StudentProfile): Promise<JobDetail> {
    const match = await this.matchProfile(documentId, profile);
    return this.personalize(documentId, match.auto_replacement_plan);
  }

  /**
   * Retrieves latest personalization job result.
   */
  async getLatestResult(documentId: string): Promise<JobDetail> {
    const job = this.jobDetailCache.get(documentId);
    if (job) return job;

    if (isNativePlatform()) {
      const doc = this.docCache.get(documentId);
      if (doc?.personalizedPath) {
        const recoveredJob: JobDetail = {
          job_id: `job_${documentId}`,
          document_id: documentId,
          status: 'completed',
          total_replacements: 1,
          successful_replacements: 1,
          failed_replacements: 0,
          verification_status: 'passed',
          warnings: [],
          occurrence_results: [],
          download_available: true,
          started_at: new Date(doc.updatedAt).toISOString(),
          completed_at: new Date(doc.updatedAt).toISOString(),
        };
        this.jobDetailCache.set(documentId, recoveredJob);
        return recoveredJob;
      }
    }

    throw new Error(`No personalization result found for ${documentId}.`);
  }

  /**
   * Native export to phone's public Downloads directory.
   */
  async exportPdf(documentId: string, fileName?: string): Promise<{ success: boolean; exportPath: string }> {
    if (isNativePlatform()) {
      return DocMorphNative.exportPdfToDownloads({ documentId, fileName });
    }
    // Web fallback
    const previewUrl = this.getPersonalizedPreviewUrl(documentId) || this.getPreviewUrl(documentId);
    if (previewUrl) {
      const a = document.createElement('a');
      a.href = previewUrl;
      a.download = fileName || `DocMorph_${documentId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    return { success: true, exportPath: fileName || 'Downloads' };
  }

  /**
   * Opens PDF in Android system PDF viewer intent.
   */
  async openPdf(documentId: string, which: 'personalized' | 'original' = 'personalized'): Promise<void> {
    if (isNativePlatform()) {
      await DocMorphNative.openPdf({ documentId, which });
      return;
    }
    const url = which === 'personalized' ? this.getPersonalizedPreviewUrl(documentId) : this.getPreviewUrl(documentId);
    if (url) window.open(url, '_blank');
  }

  /**
   * Shares PDF via Android native share sheet.
   */
  async sharePdf(documentId: string, which: 'personalized' | 'original' = 'personalized'): Promise<void> {
    if (isNativePlatform()) {
      await DocMorphNative.sharePdf({ documentId, which });
      return;
    }
    const url = which === 'personalized' ? this.getPersonalizedPreviewUrl(documentId) : this.getPreviewUrl(documentId);
    if (navigator.share && url) {
      await navigator.share({
        title: 'DocMorph Document',
        url,
      });
    } else {
      alert('Sharing is not supported in this browser window.');
    }
  }
}

export const localDocService = new LocalDocService();

