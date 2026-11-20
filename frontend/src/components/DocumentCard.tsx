import React from 'react';
import { DocumentItem, DocumentStatus } from '../types';

interface DocumentCardProps {
  document: DocumentItem;
  onOpen: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onDownload?: (id: string, name: string) => void;
  isDeleting?: boolean;
  isDownloading?: boolean;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  onOpen,
  onDelete,
  onDownload,
  isDeleting = false,
  isDownloading = false,
}) => {
  const getStatusBadge = (status: DocumentStatus, hasOutput?: boolean) => {
    if (hasOutput || status === 'completed') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold shrink-0">
          <span className="material-symbols-outlined text-[12px]">verified</span>
          Personalized
        </span>
      );
    }

    switch (status) {
      case 'uploaded':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold text-on-surface-variant shrink-0">
            <span className="material-symbols-outlined text-[12px]">schedule</span>
            Uploaded
          </span>
        );
      case 'analyzing':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary-fixed text-primary px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold animate-pulse shrink-0">
            <span className="material-symbols-outlined text-[12px] animate-spin">autorenew</span>
            Analyzing
          </span>
        );
      case 'awaiting_review':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-secondary-fixed/70 text-secondary px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold shrink-0">
            <span className="material-symbols-outlined text-[12px]">rate_review</span>
            Review
          </span>
        );
      case 'ready_to_personalize':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary-fixed/80 text-primary px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold shrink-0">
            <span className="material-symbols-outlined text-[12px]">task_alt</span>
            Ready
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary-fixed text-primary px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold shrink-0">
            <span className="material-symbols-outlined text-[12px] animate-spin">sync</span>
            Processing
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-error-container text-on-error-container px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold shrink-0">
            <span className="material-symbols-outlined text-[12px]">error</span>
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-surface-container-high px-1.5 py-0.5 text-[10px] sm:text-[11px] text-on-surface-variant shrink-0">
            {status}
          </span>
        );
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  const handleCardClick = () => {
    onOpen(document.id);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(document.id, document.original_filename);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleCardClick();
        }
      }}
      className="w-full bg-surface-container-lowest rounded-xl p-2.5 sm:p-3 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.06),0_1px_4px_-1px_rgba(15,23,42,0.04)] border border-outline-variant/60 hover:border-primary/40 active:scale-[0.99] transition-all flex items-center justify-between gap-2 cursor-pointer group select-none"
    >
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-primary-container/10 text-primary flex items-center justify-center shrink-0 shadow-xs group-hover:bg-primary-container/20 transition-colors">
          <span className="material-symbols-outlined text-[20px] sm:text-[22px]">description</span>
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <h3 className="text-xs sm:text-sm font-semibold text-on-surface truncate min-w-0">
              {document.original_filename}
            </h3>
            <span className="bg-primary/10 text-primary text-[10px] px-1.5 py-0.2 rounded font-medium shrink-0">
              PDF
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant mt-0.5 truncate">
            <span className="tabular-nums">{document.page_count} pages</span>
            <span>•</span>
            <span>{(document.file_size / 1024).toFixed(0)} KB</span>
            <span>•</span>
            <span>{formatDate(document.created_at)}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {getStatusBadge(document.status, document.has_personalized_output)}

        <button
          type="button"
          onClick={handleCardClick}
          className="h-7 sm:h-8 px-2 sm:px-2.5 rounded-full bg-primary/10 hover:bg-primary hover:text-on-primary text-primary text-[11px] sm:text-xs font-semibold flex items-center gap-0.5 sm:gap-1 transition-all active:scale-95 shrink-0"
        >
          <span>Open</span>
          <span className="material-symbols-outlined text-[14px] sm:text-[16px]">chevron_right</span>
        </button>

        {onDownload && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDownload(document.id, document.original_filename);
            }}
            disabled={isDownloading}
            className="w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center text-primary hover:bg-primary/10 rounded-full transition-colors disabled:opacity-50 shrink-0"
            title="Download PDF"
          >
            {isDownloading ? (
              <span className="material-symbols-outlined text-[16px] animate-spin text-primary">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined text-[17px]">download</span>
            )}
          </button>
        )}

        <button
          type="button"
          onClick={handleDeleteClick}
          disabled={isDeleting}
          className="w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center text-outline hover:text-error rounded-full hover:bg-error-container/30 transition-colors disabled:opacity-50 shrink-0"
          title="Delete document"
        >
          {isDeleting ? (
            <span className="material-symbols-outlined text-[16px] animate-spin text-error">progress_activity</span>
          ) : (
            <span className="material-symbols-outlined text-[16px]">delete</span>
          )}
        </button>
      </div>
    </div>
  );
};
