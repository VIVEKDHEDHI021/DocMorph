import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { api } from '../services/api';
import { SmartSelectionOverlay } from './SmartSelectionOverlay';
import { ManualDetectionResult } from '../services/nativeDocMorph';

// Configure local offline worker for standard PDF.js rendering in Vite
pdfjsLib.GlobalWorkerOptions.workerSrc = '/assets/pdf.worker.min.js';

interface PdfViewerProps {
  documentId: string;
  isPersonalized?: boolean;
  title?: string;
  className?: string;
  onSmartSelectResult?: (result: ManualDetectionResult) => void;
  onPageChange?: (page: number, total: number) => void;
}

export const PdfViewer: React.FC<PdfViewerProps> = ({
  documentId,
  isPersonalized = false,
  title,
  className = '',
  onSmartSelectResult,
  onPageChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [currentPdfPage, setCurrentPdfPage] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [isFitMode, setIsFitMode] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Smart Selection State
  const [smartSelectMode, setSmartSelectMode] = useState<'none' | 'area' | 'text'>('none');
  const [pageDimensions, setPageDimensions] = useState<{ width: number; height: number }>({
    width: 595.28,
    height: 841.89,
  });
  const [canvasDimensions, setCanvasDimensions] = useState<{ width: number; height: number }>({
    width: 595,
    height: 842,
  });

  // Calculate fit-to-width scale based on container width
  const calculateFitScale = useCallback((pdfWidth: number, viewportEl: HTMLElement | null) => {
    if (!viewportEl || !pdfWidth) return 1.0;
    const isMobile = window.innerWidth < 640;
    const margin = isMobile ? 12 : 28;
    const availableWidth = Math.max(viewportEl.clientWidth - margin, 240);
    const fitScale = availableWidth / pdfWidth;
    return Math.min(Math.max(Number(fitScale.toFixed(2)), 0.35), 2.8);
  }, []);

  // Load PDF Document bytes into PDF.js
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
        onPageChange?.(1, doc.numPages);

        const firstPage = await doc.getPage(1);
        const unscaled = firstPage.getViewport({ scale: 1.0 });
        setPageDimensions({
          width: unscaled.width,
          height: unscaled.height,
        });

        if (viewportRef.current) {
          const initialScale = calculateFitScale(unscaled.width, viewportRef.current);
          setScale(initialScale);
          setIsFitMode(true);
        }
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
  }, [documentId, isPersonalized, calculateFitScale]);

  // Auto re-fit on resize if isFitMode is active
  useEffect(() => {
    const viewportEl = viewportRef.current;
    if (!viewportEl) return;

    let resizeTimer: any = null;
    const observer = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (isFitMode && pageDimensions.width > 0) {
          const newFit = calculateFitScale(pageDimensions.width, viewportEl);
          setScale((prev) => (Math.abs(prev - newFit) > 0.02 ? newFit : prev));
        }
      }, 100);
    });

    observer.observe(viewportEl);
    return () => {
      observer.disconnect();
      clearTimeout(resizeTimer);
    };
  }, [isFitMode, pageDimensions.width, calculateFitScale]);

  // Render Page onto Canvas
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let renderTask: any = null;

    const renderPage = async () => {
      try {
        const page = await pdfDoc.getPage(currentPage);
        setCurrentPdfPage(page);
        onPageChange?.(currentPage, totalPages);

        const unscaledViewport = page.getViewport({ scale: 1.0 });
        setPageDimensions({
          width: unscaledViewport.width,
          height: unscaledViewport.height,
        });

        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        const activeScale = scale || 1.0;
        const viewport = page.getViewport({ scale: activeScale });
        const outputScale = window.devicePixelRatio || 1;

        const dispW = Math.floor(viewport.width);
        const dispH = Math.floor(viewport.height);

        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${dispW}px`;
        canvas.style.height = `${dispH}px`;

        setCanvasDimensions({ width: dispW, height: dispH });

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
  }, [pdfDoc, currentPage, scale, totalPages]);

  // Touch gesture pinch-to-zoom & double-tap handlers
  const touchStateRef = useRef<{
    startDist: number;
    startScale: number;
    lastTap: number;
  }>({
    startDist: 0,
    startScale: 1.0,
    lastTap: 0,
  });

  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    if (smartSelectMode !== 'none') return;

    if (e.touches.length === 2) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      touchStateRef.current.startDist = dist;
      touchStateRef.current.startScale = scale;
    } else if (e.touches.length === 1) {
      const now = Date.now();
      if (now - touchStateRef.current.lastTap < 300) {
        e.preventDefault();
        handleToggleFit();
        touchStateRef.current.lastTap = 0;
      } else {
        touchStateRef.current.lastTap = now;
      }
    }
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    if (smartSelectMode !== 'none') return;

    if (e.touches.length === 2 && touchStateRef.current.startDist > 0) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const factor = dist / touchStateRef.current.startDist;
      const targetScale = Math.min(Math.max(touchStateRef.current.startScale * factor, 0.4), 2.8);
      setIsFitMode(false);
      setScale(Number(targetScale.toFixed(2)));
    }
  };

  const handleTouchEnd = () => {
    touchStateRef.current.startDist = 0;
  };

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((prev) => prev - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((prev) => prev + 1);
  };

  const handleZoomIn = () => {
    setIsFitMode(false);
    setScale((prev) => Math.min(Number((prev + 0.15).toFixed(2)), 2.8));
  };

  const handleZoomOut = () => {
    setIsFitMode(false);
    setScale((prev) => Math.max(Number((prev - 0.15).toFixed(2)), 0.4));
  };

  const handleToggleFit = () => {
    if (!viewportRef.current || !pageDimensions.width) return;
    if (isFitMode) {
      setIsFitMode(false);
      setScale(1.2);
    } else {
      const fit = calculateFitScale(pageDimensions.width, viewportRef.current);
      setScale(fit);
      setIsFitMode(true);
    }
  };

  const getFormatLabel = () => {
    const w = Math.round(pageDimensions.width);
    const h = Math.round(pageDimensions.height);
    if ((w === 595 && h === 842) || (w === 842 && h === 595)) return 'A4';
    if ((w === 612 && h === 792) || (w === 792 && h === 612)) return 'Letter';
    if ((w === 612 && h === 1008) || (w === 1008 && h === 612)) return 'Legal';
    return 'PDF';
  };

  return (
    <div
      ref={containerRef}
      className={`flex flex-col w-full relative ${className}`}
    >
      {/* Interactive Canvas Controls & Status Header Pill (Matching DESIGN.md) */}
      <div className="sticky top-2 z-30 flex items-center justify-between gap-space-sm mb-space-md py-1 px-1">
        {/* Active Stage & Mode Info */}
        <div className="flex items-center gap-space-xs bg-surface-container-lowest/85 backdrop-blur-md px-3 py-1.5 rounded-full shadow-[0_2px_8px_rgba(15,23,42,0.06)] border border-surface-container-high/60">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">
            {isPersonalized ? 'Personalized Preview' : 'Continuous Render'}
          </span>
        </div>

        {/* Floating Zoom / Fit Indicator Control & Smart Select */}
        <div className="flex items-center gap-1.5 bg-surface-container-lowest/85 backdrop-blur-md px-2.5 py-1.5 rounded-full shadow-[0_2px_10px_rgba(15,23,42,0.08)] border border-surface-container-high/60">
          <button
            onClick={handleToggleFit}
            disabled={isLoading}
            className="flex items-center gap-1 text-on-surface hover:text-primary transition-colors"
            title="Toggle Fit to Width"
          >
            <span className="material-symbols-outlined text-[16px] text-primary">fit_screen</span>
            <span className="font-label-md text-label-md font-medium">
              {isFitMode ? '100% Fit' : `${Math.round(scale * 100)}%`}
            </span>
          </button>

          <span className="w-px h-3 bg-surface-container-highest mx-0.5" />

          {/* Page Selector Pill */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={handlePrevPage}
              disabled={currentPage <= 1 || isLoading}
              className="w-6 h-6 flex items-center justify-center rounded-full text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors"
              title="Previous Page"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_left</span>
            </button>
            <span className="font-label-sm text-label-sm text-on-surface px-1 min-w-[36px] text-center font-semibold">
              {currentPage}/{totalPages}
            </span>
            <button
              onClick={handleNextPage}
              disabled={currentPage >= totalPages || isLoading}
              className="w-6 h-6 flex items-center justify-center rounded-full text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors"
              title="Next Page"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
            </button>
          </div>

          <span className="w-px h-3 bg-surface-container-highest mx-0.5" />

          {/* Smart Select Toggle */}
          {smartSelectMode === 'none' ? (
            <button
              onClick={() => setSmartSelectMode('area')}
              disabled={isLoading || !!error}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-primary to-secondary text-on-primary font-label-sm text-label-sm shadow-xs transition-transform active:scale-95 disabled:opacity-50"
              title="Smart Select Credentials"
            >
              <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
              <span className="hidden xs:inline">Select</span>
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={() => setSmartSelectMode('area')}
                className={`px-2 py-0.5 rounded-full font-label-sm text-label-sm ${
                  smartSelectMode === 'area'
                    ? 'bg-primary text-on-primary font-bold'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Area
              </button>
              <button
                onClick={() => setSmartSelectMode('text')}
                className={`px-2 py-0.5 rounded-full font-label-sm text-label-sm ${
                  smartSelectMode === 'text'
                    ? 'bg-primary text-on-primary font-bold'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Text
              </button>
              <button
                onClick={() => setSmartSelectMode('none')}
                className="w-5 h-5 flex items-center justify-center rounded-full text-outline hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-[14px]">close</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* CONTINUOUS VERTICAL PDF VIEWER CANVAS */}
      <div
        ref={viewportRef}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        className="flex flex-col w-full items-center gap-0 relative overflow-visible"
      >
        {isLoading && (
          <div className="flex flex-col items-center justify-center gap-3 text-on-surface-variant py-24">
            <span className="material-symbols-outlined text-[36px] text-primary animate-spin">progress_activity</span>
            <span className="font-label-md text-label-md font-semibold text-on-surface">Rendering high-precision canvas...</span>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center gap-3 text-error max-w-sm text-center py-20 px-4 bg-surface-container-lowest rounded-xl border border-error-container">
            <span className="material-symbols-outlined text-[36px]">error</span>
            <span className="font-label-lg text-label-lg font-bold">Preview Unavailable</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">{error}</span>
          </div>
        )}

        {/* PAGE CONTAINER (Matching Level 1 Document Card with Margin Bar) */}
        <div
          className={`w-full bg-surface-container-lowest rounded-xl shadow-[0_2px_12px_-2px_rgba(15,23,42,0.08),0_1px_4px_-1px_rgba(15,23,42,0.04)] overflow-hidden relative border border-outline-variant/50 transition-all ${
            isLoading || error ? 'hidden' : 'block'
          }`}
        >
          {/* PDF Canvas Header / Margin Bar */}
          <div className="bg-surface-container-high/40 px-space-md py-2 flex items-center justify-between border-b border-surface-container-high/60">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-primary/20 flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              </span>
              <span className="font-label-sm text-label-sm text-on-surface-variant font-semibold tracking-wider uppercase">
                PAGE {currentPage} OF {totalPages}
              </span>
            </div>
            <span className="font-body-sm text-body-sm text-outline">
              {getFormatLabel()} • {Math.round(pageDimensions.width)} × {Math.round(pageDimensions.height)} pt
            </span>
          </div>

          {/* Rendered Canvas & Smart Selection Layer */}
          <div className="relative flex items-center justify-center p-space-sm sm:p-space-md overflow-auto bg-surface-container-low/20">
            <div className="relative inline-block shadow-sm rounded-md overflow-hidden bg-white">
              <canvas
                ref={canvasRef}
                className="block select-none"
              />

              {smartSelectMode !== 'none' && !isLoading && !error && (
                <SmartSelectionOverlay
                  documentId={documentId}
                  pageIndex={currentPage - 1}
                  pageWidth={pageDimensions.width}
                  pageHeight={pageDimensions.height}
                  canvasWidth={canvasDimensions.width}
                  canvasHeight={canvasDimensions.height}
                  scale={scale}
                  mode={smartSelectMode}
                  pdfPage={currentPdfPage}
                  onClose={() => setSmartSelectMode('none')}
                  onResult={onSmartSelectResult}
                />
              )}
            </div>
          </div>
        </div>

        {/* CONTINUOUS PAGE SEPARATION DIVIDER (When multi-page document) */}
        {totalPages > 1 && currentPage < totalPages && !isLoading && !error && (
          <div className="w-full py-5 flex items-center justify-center gap-space-sm relative">
            <div className="h-0.5 flex-1 bg-surface-container-high rounded-full" />
            <button
              onClick={handleNextPage}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm shadow-sm hover:bg-surface-container-high hover:text-on-surface transition-colors active:scale-95"
            >
              <span className="material-symbols-outlined text-[14px]">expand_more</span>
              <span>NEXT PAGE ({currentPage + 1})</span>
            </button>
            <div className="h-0.5 flex-1 bg-surface-container-high rounded-full" />
          </div>
        )}
      </div>
    </div>
  );
};
