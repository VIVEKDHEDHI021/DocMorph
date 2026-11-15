import { registerPlugin, Capacitor } from '@capacitor/core';

export interface StudentProfileData {
  fullName: string;
  enrollmentNumber: string;
  rollNumber?: string | null;
  studentId?: string | null;
  updatedAt?: string;
}

export interface ImportPdfResult {
  success: boolean;
  documentId: string;
  fileName: string;
  filePath: string;
  pageCount: number;
  fileSizeBytes: number;
}

export interface NativeTextBlock {
  text: string;
  bbox: number[]; // [x0, y0, x1, y1] normalized to [0, 1000]
  rawBbox: number[]; // [x0, y0, x1, y1] in PDF points
  fontName?: string;
  fontSize?: number;
}

export interface NativePageResult {
  pageNumber: number;
  width: number;
  height: number;
  isScanned: boolean;
  blocks: NativeTextBlock[];
}

export interface ExtractionResult {
  documentId: string;
  totalPages: number;
  isScanned: boolean;
  pages: NativePageResult[];
}

export interface DetectionCandidate {
  id: string;
  fieldType: string; // "student_name", "enrollment_number", "roll_number", "student_id"
  detectedText: string;
  replacementText?: string | null;
  confidence: number;
  pageIndex: number;
  normalizedBox: number[]; // [x0, y0, x1, y1] normalized [0, 1000]
  pdfPointBox: number[]; // [x0, y0, x1, y1] in PDF points
  fontName?: string | null;
  fontSize?: number;
  pairId?: string | null;
  requiresConfirmation: boolean;
}

export interface DocumentAnalysisResult {
  documentId: string;
  totalPages: number;
  isScanned: boolean;
  candidates: DetectionCandidate[];
}

export interface DocumentRecord {
  documentId: string;
  fileName: string;
  originalPath: string;
  personalizedPath?: string | null;
  pageCount: number;
  isScanned: boolean;
  fileSizeBytes: number;
  status: string;
  createdAt: number;
  updatedAt: number;
}

export interface PersonalizationResult {
  success: boolean;
  documentId: string;
  personalizedPath: string;
  personalizedPreviewUrl: string;
  totalReplaced: number;
  originalSha256: string;
  personalizedSha256: string;
  verificationPassed: boolean;
  warnings: string[];
}

export interface ManualSelectionInput {
  documentId: string;
  filePath?: string;
  pageIndex: number;
  selectionType: 'area' | 'text';
  pageWidth: number;
  pageHeight: number;
  rawBbox?: number[]; // [x0, y0, x1, y1] in points
  normalizedBox?: number[]; // [x0, y0, x1, y1] in [0, 1000]
  selectedText?: string;
}

export interface ManualDetectionResult {
  documentId: string;
  pageIndex: number;
  selectionType: 'area' | 'text';
  resolvedPdfBox: number[];
  extractedText: string;
  footerStatus: 'FOOTER_CONFIRMED' | 'FOOTER_NOT_FOUND' | 'FOOTER_UNCERTAIN' | 'DOCUMENT_UNREADABLE';
  confidence: number;
  candidates: DetectionCandidate[];
  negativeReasons: string[];
  summaryMessage: string;
}

export interface DocMorphNativePlugin {
  saveProfile(options: {
    fullName: string;
    enrollmentNumber: string;
    rollNumber?: string;
    studentId?: string;
  }): Promise<{ success: boolean }>;

  getProfile(): Promise<{
    hasProfile: boolean;
    profile: StudentProfileData | null;
  }>;

  deleteProfile(): Promise<{ success: boolean }>;

  importPdfFromUri(options: { uri: string }): Promise<ImportPdfResult>;

  importPdfFromBase64(options: { base64Data: string; fileName?: string }): Promise<ImportPdfResult>;

  extractPdfData(options: {
    documentId: string;
    filePath: string;
  }): Promise<ExtractionResult>;

  analyzeDocument(options: {
    documentId: string;
    filePath: string;
  }): Promise<DocumentAnalysisResult>;

  manualDetect(options: ManualSelectionInput): Promise<ManualDetectionResult>;

  matchProfile(options: {
    documentId: string;
  }): Promise<{ documentId: string; candidates: DetectionCandidate[] }>;

  personalizeDocument(options: {
    documentId: string;
    confirmedCandidates?: any[];
  }): Promise<PersonalizationResult>;

  exportPdfToDownloads(options: {
    documentId: string;
    fileName?: string;
  }): Promise<{ success: boolean; exportPath: string }>;

  openPdf(options: {
    documentId: string;
    which?: 'personalized' | 'original';
  }): Promise<{ success: boolean }>;

  sharePdf(options: {
    documentId: string;
    which?: 'personalized' | 'original';
  }): Promise<{ success: boolean }>;

  getPreviewUrl(options: { filePath: string }): Promise<{ url: string; filePath: string }>;

  getPdfBase64(options: {
    documentId?: string;
    filePath?: string;
    which?: 'personalized' | 'original';
  }): Promise<{ base64: string; size: number }>;

  listDocuments(): Promise<{ documents: DocumentRecord[] }>;

  deleteDocument(options: { documentId: string }): Promise<{ success: boolean }>;
}

export const DocMorphNative = registerPlugin<DocMorphNativePlugin>('DocMorphNative');

export const isNativePlatform = (): boolean => {
  return Capacitor.isNativePlatform();
};
