// API Client Service for DocMorph (100% On-Device & Offline)
// Routes all document operations directly to localDocService (DocMorphNative)
// Zero runtime HTTP requests to FastAPI or remote endpoints.

import {
  AuthResponse,
  DocumentDetectionResponse,
  DocumentItem,
  DocumentListResponse,
  JobDetail,
  ProfileMatchResult,
  StudentProfile,
  User,
} from '../types';
import { localDocService } from './localDocService';
import { profileStorage } from './profileStorage';
import { ManualSelectionInput, ManualDetectionResult } from './nativeDocMorph';

export function getApiBaseUrl(): string {
  return 'http://localhost';
}

class ApiClient {
  private token: string | null = 'offline_local_token';

  constructor() {
    this.token = localStorage.getItem('docmorph_token') || 'offline_local_token';
  }

  setToken(token: string | null) {
    this.token = token || 'offline_local_token';
    if (token) {
      localStorage.setItem('docmorph_token', token);
    } else {
      localStorage.removeItem('docmorph_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  async ensureSession(): Promise<string> {
    return this.token || 'offline_local_token';
  }

  // Authentication & Sessions (100% Offline / Local profile)
  auth = {
    anonymousSession: async (): Promise<AuthResponse> => {
      const p = await profileStorage.getProfile();
      const user: User = {
        id: 'device_owner',
        email: 'offline@device.local',
        full_name: p?.full_name || 'Device Owner',
        is_active: true,
        created_at: p?.created_at || new Date(0).toISOString(),
      };
      return {
        access_token: 'offline_local_token',
        token_type: 'bearer',
        user,
      };
    },

    signup: async (data: { email: string; password: string; full_name?: string }): Promise<User> => {
      if (data.full_name) {
        const existing = await profileStorage.getProfile();
        await profileStorage.saveProfile({
          full_name: data.full_name,
          enrollment_number: existing?.enrollment_number || 'PENDING',
        });
      }
      return {
        id: 'device_owner',
        email: data.email || 'offline@device.local',
        full_name: data.full_name || 'Device Owner',
        is_active: true,
        created_at: new Date().toISOString(),
      };
    },

    login: async (_data: { email: string; password: string }): Promise<AuthResponse> => {
      return this.auth.anonymousSession();
    },

    getMe: async (): Promise<User> => {
      const res = await this.auth.anonymousSession();
      return res.user;
    },
  };

  // Documents (delegates to localDocService / DocMorphNative)
  documents = {
    upload: async (file: File): Promise<DocumentItem> => {
      return localDocService.upload(file);
    },

    list: async (page = 1, pageSize = 50): Promise<DocumentListResponse> => {
      return localDocService.list(page, pageSize);
    },

    getDetail: async (documentId: string): Promise<DocumentItem> => {
      return localDocService.getDetail(documentId);
    },

    delete: async (documentId: string): Promise<void> => {
      return localDocService.delete(documentId);
    },

    getPreviewUrl: (documentId: string): string => {
      return localDocService.getPreviewUrl(documentId);
    },

    getPdfArrayBuffer: async (documentId: string, isPersonalized = false): Promise<ArrayBuffer> => {
      return localDocService.getPdfArrayBuffer(documentId, isPersonalized);
    },

    getPdfBlob: async (documentId: string, isPersonalized = false): Promise<Blob> => {
      return localDocService.getPdfBlob(documentId, isPersonalized);
    },
  };

  // Detections
  detections = {
    analyze: async (documentId: string): Promise<DocumentDetectionResponse> => {
      return localDocService.analyze(documentId);
    },

    getDetections: async (documentId: string): Promise<DocumentDetectionResponse> => {
      return localDocService.getDetections(documentId);
    },

    reviewField: async (
      documentId: string,
      fieldId: string,
      action: { review_status: string; corrected_value?: string; field_type?: string }
    ): Promise<any> => {
      return localDocService.reviewField(documentId, fieldId, action);
    },

    confirmField: async (documentId: string, fieldId: string): Promise<any> => {
      return localDocService.confirmField(documentId, fieldId);
    },

    rejectField: async (documentId: string, fieldId: string): Promise<any> => {
      return localDocService.rejectField(documentId, fieldId);
    },

    manualDetect: async (input: ManualSelectionInput): Promise<ManualDetectionResult> => {
      return localDocService.manualDetect(input);
    },
  };

  // Personalization
  personalization = {
    personalize: async (
      documentId: string,
      replacements: { field_id: string; field_type: string; new_value: string }[]
    ): Promise<JobDetail> => {
      return localDocService.personalize(documentId, replacements);
    },

    matchProfile: async (documentId: string, profile: StudentProfile): Promise<ProfileMatchResult> => {
      return localDocService.matchProfile(documentId, profile);
    },

    autoPersonalize: async (documentId: string, profile: StudentProfile): Promise<JobDetail> => {
      return localDocService.autoPersonalize(documentId, profile);
    },

    getJobStatus: async (jobId: string): Promise<JobDetail> => {
      const docId = jobId.replace(/^job_/, '');
      return localDocService.getLatestResult(docId);
    },

    getLatestResult: async (documentId: string): Promise<JobDetail> => {
      return localDocService.getLatestResult(documentId);
    },

    getDownloadUrl: (documentId: string): string => {
      return localDocService.getPersonalizedPreviewUrl(documentId);
    },

    getPersonalizedPreviewUrl: (documentId: string): string => {
      return localDocService.getPersonalizedPreviewUrl(documentId);
    },

    getPdfArrayBuffer: async (documentId: string): Promise<ArrayBuffer> => {
      return localDocService.getPdfArrayBuffer(documentId, true);
    },

    getPdfBlob: async (documentId: string): Promise<Blob> => {
      return localDocService.getPdfBlob(documentId, true);
    },

    exportPdf: async (documentId: string, fileName?: string): Promise<{ success: boolean; exportPath: string }> => {
      return localDocService.exportPdf(documentId, fileName);
    },

    openPdf: async (documentId: string, which: 'personalized' | 'original' = 'personalized'): Promise<void> => {
      return localDocService.openPdf(documentId, which);
    },

    sharePdf: async (documentId: string, which: 'personalized' | 'original' = 'personalized'): Promise<void> => {
      return localDocService.sharePdf(documentId, which);
    },
  };
}

export const api = new ApiClient();
