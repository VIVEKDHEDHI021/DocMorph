import React, { useState } from 'react';
import {
  User,
  Hash,
  CreditCard,
  Layers,
  Check,
  X,
  Edit2,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { DetectionField } from '../types';
import { ConfidenceBadge, ReviewStatusBadge } from './VerificationBadge';

interface DetectionFieldCardProps {
  field: DetectionField;
  onConfirm: (fieldId: string) => void;
  onReject: (fieldId: string) => void;
  onCorrect: (fieldId: string, correctedValue: string, fieldType?: string) => void;
}

export const DetectionFieldCard: React.FC<DetectionFieldCardProps> = ({
  field,
  onConfirm,
  onReject,
  onCorrect,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(field.suggested_value);
  const [editType, setEditType] = useState(field.field_type);
  const [showReasons, setShowReasons] = useState(false);

  const getFieldIcon = (type: string) => {
    switch (type) {
      case 'student_name':
        return <User className="h-5 w-5 text-brand-600" />;
      case 'enrollment_number':
        return <Hash className="h-5 w-5 text-indigo-600" />;
      case 'roll_number':
        return <Layers className="h-5 w-5 text-emerald-600" />;
      case 'student_id':
        return <CreditCard className="h-5 w-5 text-amber-600" />;
      default:
        return <User className="h-5 w-5 text-slate-600" />;
    }
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

  const handleSaveCorrection = () => {
    onCorrect(field.field_id, editValue, editType);
    setIsEditing(false);
  };

  const isConfirmed = field.review_status === 'confirmed';
  const isCorrected = field.review_status === 'corrected';
  const isRejected = field.review_status === 'rejected';

  return (
    <div
      className={`rounded-2xl border transition-all p-5 shadow-sm ${
        isConfirmed
          ? 'border-emerald-200 bg-emerald-50/20'
          : isCorrected
          ? 'border-blue-200 bg-blue-50/20'
          : isRejected
          ? 'border-rose-200 bg-rose-50/20 opacity-70'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        {/* Left: Field Info */}
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-xl bg-slate-100/80 border border-slate-200/60 mt-0.5">
            {getFieldIcon(field.field_type)}
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                {getFieldLabel(field.field_type)}
              </span>
              <span className="text-xs font-mono text-slate-400">({field.field_id})</span>
            </div>

            {isEditing ? (
              <div className="pt-2 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    Correct Value:
                  </label>
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-full sm:w-80 px-3 py-1.5 text-sm border border-brand-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                    placeholder="Enter corrected value"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    Field Type:
                  </label>
                  <select
                    value={editType}
                    onChange={(e) => setEditType(e.target.value as any)}
                    className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                  >
                    <option value="student_name">Student Name</option>
                    <option value="enrollment_number">Enrollment Number</option>
                    <option value="roll_number">Roll Number</option>
                    <option value="student_id">Student ID</option>
                  </select>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={handleSaveCorrection}
                    className="px-3 py-1 text-xs font-semibold text-white bg-brand-600 rounded-md hover:bg-brand-700 transition-colors"
                  >
                    Save Correction
                  </button>
                  <button
                    onClick={() => setIsEditing(false)}
                    className="px-3 py-1 text-xs font-medium text-slate-600 hover:text-slate-900"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div className="text-lg font-bold text-slate-900 tracking-tight">
                  {field.suggested_value}
                </div>
                {isCorrected && (
                  <div className="text-xs text-slate-500 mt-0.5">
                    Original detected:{' '}
                    <span className="line-through font-mono">{field.original_value}</span>
                  </div>
                )}
              </div>
            )}

            {/* Badges and Occurrence Pages */}
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <ConfidenceBadge level={field.confidence_level} score={field.confidence} />
              <ReviewStatusBadge status={field.review_status} />
              <div className="inline-flex items-center gap-1 text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                <span>
                  {field.occurrences_count} {field.occurrences_count === 1 ? 'page' : 'pages'}: [
                  {field.pages.join(', ')}]
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        {!isEditing && (
          <div className="flex items-center gap-2 sm:self-center border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100">
            <button
              onClick={() => onConfirm(field.field_id)}
              disabled={isConfirmed}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                isConfirmed
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200/80'
              }`}
              title="Confirm detection as accurate"
            >
              <Check className="h-3.5 w-3.5" />
              {isConfirmed ? 'Confirmed' : 'Confirm'}
            </button>

            <button
              onClick={() => setIsEditing(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              title="Correct value or type"
            >
              <Edit2 className="h-3.5 w-3.5" />
              Edit
            </button>

            <button
              onClick={() => onReject(field.field_id)}
              disabled={isRejected}
              className={`p-1.5 text-xs rounded-lg transition-colors ${
                isRejected
                  ? 'bg-rose-600 text-white'
                  : 'text-slate-400 hover:text-rose-600 hover:bg-rose-50'
              }`}
              title="Reject field (will not be replaced)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Expandable Confidence Reasons Dropdown */}
      {field.reasons && field.reasons.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          <button
            onClick={() => setShowReasons(!showReasons)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-brand-600 transition-colors font-medium"
          >
            <Info className="h-3.5 w-3.5" />
            <span>Detection Reasons ({field.reasons.length})</span>
            {showReasons ? (
              <ChevronUp className="h-3.5 w-3.5 ml-0.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 ml-0.5" />
            )}
          </button>

          {showReasons && (
            <ul className="mt-2 pl-5 list-disc space-y-1 text-xs text-slate-600 bg-slate-50/80 p-3 rounded-lg border border-slate-100">
              {field.reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

