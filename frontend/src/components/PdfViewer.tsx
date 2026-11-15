import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Loader2,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { api } from '../services/api';

// Configure local offline worker for standard PDF.js rendering in Vite
pdfjsLib.GlobalWorkerOptions.workerSrc = '/assets/pdf.worker.min.js';

interface PdfViewerProps {
  documentId: string;
  isPersonalized?: boolean;
  title?: string;
  className?: string;
}

export const PdfViewer: React.FC<PdfViewerProps> = ({
  documentId,
  isPersonalized = false,
  title,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.2);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load PDF Document bytes directly into PDF.js
  useEffect(() => {
    let isCancelled = false;

    const loadPdf = async () => {
      if (!documentId) return;
      setIsLoading(true);
      setError(null);
      try {
        const arrayBuffer = await api.documents.getPdfArrayBuffer(documentId, isPersonalized);
        if (isCancelled) return;

        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const doc = await loadingTask.promise;

        if (isCancelled) return;
        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setCurrentPage(1);
      } catch (err: any) {
        if (!isCancelled) {
          setError(err.message || 'Unable to render PDF preview.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      isCancelled = true;
    };
  }, [documentId, isPersonalized]);

  // Render Page onto Canvas
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let renderTask: any = null;

    const renderPage = async () => {
      try {
        const page = await pdfDoc.getPage(currentPage);
        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        const viewport = page.getViewport({ scale });
        const outputScale = window.devicePixelRatio || 1;

        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined;

        const renderContext = {
          canvasContext: context,
          transform: transform,
          viewport: viewport,
        };

        renderTask = page.render(renderContext);
        await renderTask.promise;
      } catch (err: any) {
        if (err.name !== 'RenderingCancelledException') {
          console.error('Error rendering page:', err);
        }
      }
    };

    renderPage();

    return () => {
      if (renderTask) {
        renderTask.cancel();
      }
    };
  }, [pdfDoc, currentPage, scale]);

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((prev) => prev - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((prev) => prev + 1);
  };

  const handleZoomIn = () => setScale((prev) => Math.min(prev + 0.2, 2.5));
  const handleZoomOut = () => setScale((prev) => Math.max(prev - 0.2, 0.6));
  const handleFitWidth = () => {
    if (containerRef.current) {
      const containerWidth = containerRef.current.clientWidth - 48; // padding
      setScale(containerWidth / 600);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`flex flex-col rounded-2xl border border-slate-200 bg-slate-900/5 shadow-inner overflow-hidden ${className}`}
    >
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5 gap-2">
        <div className="flex items-center gap-2">
          {isPersonalized ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80">
              <FileCheck className="h-3.5 w-3.5 text-emerald-600" />
              Verified Personalized PDF
            </span>
          ) : (
            <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
              {title || 'Original Source PDF'}
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1 sm:gap-2">
          {/* Page Navigation */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 border border-slate-200/60">
            <button
              onClick={handlePrevPage}
              disabled={currentPage <= 1 || isLoading}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
              title="Previous Page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs font-medium text-slate-700 px-2 min-w-[70px] text-center">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={handleNextPage}
              disabled={currentPage >= totalPages || isLoading}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
              title="Next Page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="h-4 w-px bg-slate-200 mx-1 hidden sm:block" />

          {/* Zoom Controls */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 border border-slate-200/60">
            <button
              onClick={handleZoomOut}
              disabled={isLoading || scale <= 0.6}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-40 transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="text-xs font-medium text-slate-700 px-1.5 min-w-[45px] text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              disabled={isLoading || scale >= 2.5}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-40 transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              onClick={handleFitWidth}
              disabled={isLoading}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-40 transition-colors"
              title="Fit to Width"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div className="relative flex-1 overflow-auto p-4 sm:p-6 flex items-center justify-center min-h-[450px] max-h-[750px] bg-slate-200/60">
        {isLoading && (
          <div className="flex flex-col items-center justify-center gap-3 text-slate-500 py-16">
            <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
            <span className="text-sm font-medium">Rendering PDF page...</span>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center gap-3 text-rose-600 max-w-sm text-center py-16">
            <AlertCircle className="h-8 w-8 text-rose-500" />
            <span className="text-sm font-semibold">Preview Unavailable</span>
            <span className="text-xs text-slate-600">{error}</span>
          </div>
        )}

        <canvas
          ref={canvasRef}
          className={`rounded-lg bg-white shadow-2xl transition-transform duration-150 ${
            isLoading || error ? 'hidden' : 'block'
          }`}
        />
      </div>
    </div>
  );
};

