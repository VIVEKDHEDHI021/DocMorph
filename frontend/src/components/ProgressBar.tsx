import React from 'react';
import { CheckCircle2, Loader2, Circle } from 'lucide-react';

interface Stage {
  id: string;
  label: string;
  description: string;
}

const STAGES: Stage[] = [
  {
    id: 'prepare',
    label: 'Preparing Document',
    description: 'Loading validated source PDF and confirmed fields',
  },
  {
    id: 'redact',
    label: 'Applying Redactions & Typography',
    description: 'Purging old text streams and fitting adaptive font size',
  },
  {
    id: 'verify',
    label: 'Verifying Output',
    description: 'Validating PDF structure, bounding boxes, and label retention',
  },
  {
    id: 'finalize',
    label: 'Finalizing PDF',
    description: 'Generating verified download package',
  },
];

interface ProgressBarProps {
  currentStageIndex: number;
  isComplete?: boolean;
  error?: string | null;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  currentStageIndex,
  isComplete = false,
  error = null,
}) => {
  return (
    <div className="w-full max-w-xl mx-auto py-6">
      <div className="space-y-4">
        {STAGES.map((stage, idx) => {
          const isDone = isComplete || idx < currentStageIndex;
          const isCurrent = !isComplete && idx === currentStageIndex;
          const isPending = !isComplete && idx > currentStageIndex;

          return (
            <div
              key={stage.id}
              className={`flex items-start gap-3.5 p-3.5 rounded-xl border transition-all ${
                isCurrent
                  ? 'border-brand-500 bg-brand-50/40 shadow-sm'
                  : isDone
                  ? 'border-emerald-200 bg-emerald-50/20'
                  : 'border-slate-100 bg-white/50 opacity-60'
              }`}
            >
              <div className="mt-0.5">
                {isDone ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : isCurrent ? (
                  <Loader2 className="h-5 w-5 text-brand-600 animate-spin" />
                ) : (
                  <Circle className="h-5 w-5 text-slate-300" />
                )}
              </div>
              <div className="space-y-0.5">
                <div
                  className={`text-sm font-semibold ${
                    isCurrent
                      ? 'text-brand-900'
                      : isDone
                      ? 'text-emerald-900'
                      : 'text-slate-500'
                  }`}
                >
                  {stage.label}
                </div>
                <div className="text-xs text-slate-500">{stage.description}</div>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mt-4 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          Processing failed: {error}
        </div>
      )}
    </div>
  );
};

