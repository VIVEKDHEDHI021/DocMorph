// Core Domain Types for DocMorph Frontend

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type DocumentStatus =
  | 'uploaded'
  | 'analyzing'
  | 'awaiting_review'
  | 'ready_to_personalize'
  | 'processing'
  | 'completed'
  | 'failed';

export interface DocumentItem {
  id: string;
  original_filename: string;
  page_count: number;
  file_size: number;
  status: DocumentStatus;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  detections_count?: number;
  has_personalized_output?: boolean;
  latest_job_id?: string | null;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface DetectionOccurrence {
  page_number: number;
  raw_text: string;
  bbox: Record<string, number>;
  value_bbox: Record<string, number>;
  label_bbox: Record<string, number>;
}

export type ReviewStatus = 'pending' | 'confirmed' | 'corrected' | 'rejected';
export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface DetectionField {
  id: string;
  field_id: string;
  field_type: 'student_name' | 'enrollment_number' | 'roll_number' | 'student_id';
  original_value: string;
  suggested_value: string;
  corrected_value?: string | null;
  confidence: number;
  confidence_level: ConfidenceLevel;
  review_status: ReviewStatus;
  is_ambiguous: boolean;
  reasons: string[];
  occurrences_count: number;
  pages: number[];
  occurrences: DetectionOccurrence[];
}

export interface DetectionSummary {
  total_fields: number;
  high_confidence: number;
  medium_confidence: number;
  low_confidence: number;
  review_required: number;
  conflicts_count: number;
}

export interface DocumentDetectionResponse {
  document_id: string;
  status: DocumentStatus;
  fields: DetectionField[];
  summary: DetectionSummary;
}

export interface JobOccurrenceResult {
  page_number: number;
  field_id: string;
  status: 'success' | 'warning' | 'failed';
  message: string;
  warning?: string | null;
  inserted_value: string;
}

export interface VerificationReport {
  is_valid: boolean;
  page_count_matches: boolean;
  expected_pages: number;
  actual_pages: number;
  replacements_verified: number;
  total_replacements: number;
  purged_values_absent: boolean;
  labels_intact: boolean;
  unrelated_content_intact: boolean;
  details: string[];
}

export interface JobDetail {
  job_id: string;
  document_id: string;
  status: 'processing' | 'completed' | 'failed';
  total_replacements: number;
  successful_replacements: number;
  failed_replacements: number;
  verification_status: 'passed' | 'failed' | 'pending';
  warnings: string[];
  occurrence_results: JobOccurrenceResult[];
  verification_report?: VerificationReport | null;
  download_available: boolean;
  started_at: string;
  completed_at?: string | null;
}

export type ProfileMatchStatus =
  | 'already_matching'
  | 'different'
  | 'not_detected'
  | 'uncertain'
  | 'conflicting'
  | 'optional_field_empty';

export interface StudentProfile {
  full_name: string;
  enrollment_number: string;
  roll_number?: string | null;
  student_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface FieldMatchComparison {
  field_type: string;
  detected_value?: string | null;
  profile_value?: string | null;
  status: ProfileMatchStatus;
  confidence: number;
  field_id?: string | null;
  auto_action_eligible: boolean;
  reason: string;
}

export interface ProfileMatchResult {
  document_id: string;
  comparisons: Record<string, FieldMatchComparison>;
  all_eligible_for_auto: boolean;
  has_conflicts: boolean;
  requires_manual_review: boolean;
  auto_replacement_plan: { field_id: string; field_type: string; new_value: string }[];
  summary_message: string;
}

