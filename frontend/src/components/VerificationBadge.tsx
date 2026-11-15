import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, ShieldCheck } from 'lucide-react';
import { ConfidenceLevel, ReviewStatus } from '../types';

interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
  score?: number;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ level, score }) => {
  switch (level) {
    case 'high':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          High {score !== undefined && `(${Math.round(score * 100)}%)`}
        </span>
      );
    case 'medium':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
          Medium {score !== undefined && `(${Math.round(score * 100)}%)`}
        </span>
      );
    case 'low':
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          Low / Review {score !== undefined && `(${Math.round(score * 100)}%)`}
        </span>
      );
  }
};

interface ReviewStatusBadgeProps {
  status: ReviewStatus;
}

export const ReviewStatusBadge: React.FC<ReviewStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'confirmed':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          Confirmed
        </span>
      );
    case 'corrected':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
          <ShieldCheck className="h-3.5 w-3.5 text-blue-600" />
          Corrected
        </span>
      );
    case 'rejected':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          Rejected
        </span>
      );
    case 'pending':
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
          Pending Review
        </span>
      );
  }
};

