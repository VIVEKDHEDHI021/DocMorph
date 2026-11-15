import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Sparkles,
  RotateCcw,
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  AlertCircle,
  Loader2,
  Scan,
  Type,
  Maximize2,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../services/api';
import { ManualDetectionResult } from '../services/nativeDocMorph';

export interface BoundingBoxPdf {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

interface TextSpanItem {
  id: string;
  text: string;
  bbox: BoundingBoxPdf;
}

interface SmartSelectionOverlayProps {
  documentId: string;
  pageIndex: number; // 0-based
  pageWidth: number; // PDF points
  pageHeight: number; // PDF points
  canvasWidth: number; // Display pixels
  canvasHeight: number; // Display pixels
  scale: number;
  mode: 'area' | 'text';
  pdfPage?: any; // PDF.js PDFPageProxy
  onClose: () => void;
  onResult?: (result: ManualDetectionResult) => void;
}

type DragHandle = 'tl' | 'tr' | 'bl' | 'br' | 'move' | 'create';

export const SmartSelectionOverlay: React.FC<SmartSelectionOverlayProps> = ({
  documentId,
  pageIndex,
  pageWidth,
  pageHeight,
  canvasWidth,
  canvasHeight,
  scale,
  mode,
  pdfPage,
  onClose,
  onResult,
}) => {
  // Selection box in PDF points (invariant across zoom/scale changes)
  const [boxPdf, setBoxPdf] = useState<BoundingBoxPdf | null>(null);
  const [selectedText, setSelectedText] = useState<string>('');
  const [textSpans, setTextSpans] = useState<TextSpanItem[]>([]);
  const [selectedSpanIds, setSelectedSpanIds] = useState<Set<string>>(new Set());

  // Interaction dragging states
  const [dragHandle, setDragHandle] = useState<DragHandle | null>(null);
  const dragStartRef = useRef<{ x: number; y: number; origBox: BoundingBoxPdf | null }>({
    x: 0,
    y: 0,
    origBox: null,
  });

  // Analysis state & race-condition prevention
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [detectionResult, setDetectionResult] = useState<ManualDetectionResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const requestSeqRef = useRef<number>(0);

  const overlayRef = useRef<HTMLDivElement | null>(null);

  // Load text spans from PDF.js page for text selection mode
  useEffect(() => {
    let isCancelled = false;

    const extractText = async () => {
      if (!pdfPage || mode !== 'text') return;
      try {
        const textContent = await pdfPage.getTextContent();
        if (isCancelled) return;

        const spans: TextSpanItem[] = [];
        textContent.items.forEach((item: any, idx: number) => {
          if (!item.str || item.str.trim() === '') return;

          // PDF.js transform: [scaleX, skewY, skewX, scaleY, tx, ty]
          const tx = item.transform[4];
          const ty = item.transform[5];
          const w = item.width || 0;
          const h = item.height || Math.abs(item.transform[3]) || 10;

          // Convert PDF coordinate frame (origin at bottom-left) to top-left
          const x0 = tx;
          const y0 = pageHeight - ty - h;
          const x1 = tx + w;
          const y1 = pageHeight - ty;

          spans.push({
            id: `span_${idx}`,
            text: item.str,
            bbox: { x0, y0, x1, y1 },
          });
        });

        if (!isCancelled) {
          setTextSpans(spans);
        }
      } catch (err) {
        console.warn('Failed to extract text content for text selection:', err);
      }
    };

    extractText();

    return () => {
      isCancelled = true;
    };
  }, [pdfPage, pageHeight, mode]);

  // Convert client pointer coordinates to PDF points
  const clientToPdfPoint = useCallback(
    (clientX: number, clientY: number): { x: number; y: number } => {
      if (!overlayRef.current) return { x: 0, y: 0 };
      const rect = overlayRef.current.getBoundingClientRect();
      const pxX = Math.max(0, Math.min(rect.width, clientX - rect.left));
      const pxY = Math.max(0, Math.min(rect.height, clientY - rect.top));

      // Coordinate transformation:
      // pdf_x = (canvas_px / scale)
      // pdf_y = (canvas_py / scale)
      const pdfX = pxX / scale;
      const pdfY = pxY / scale;

      return {
        x: Math.max(0, Math.min(pageWidth, pdfX)),
        y: Math.max(0, Math.min(pageHeight, pdfY)),
      };
    },
    [scale, pageWidth, pageHeight]
  );

  // Pointer Down (Start Creating or Dragging)
  const handlePointerDown = (e: React.PointerEvent, handle: DragHandle) => {
    e.stopPropagation();
    e.preventDefault();

    const pt = clientToPdfPoint(e.clientX, e.clientY);
    setDragHandle(handle);
    dragStartRef.current = {
      x: pt.x,
      y: pt.y,
      origBox: boxPdf ? { ...boxPdf } : null,
    };

    if (handle === 'create') {
      setBoxPdf({
        x0: pt.x,
        y0: pt.y,
        x1: pt.x,
        y1: pt.y,
      });
      setSelectedText('');
      setDetectionResult(null);
      setAnalysisError(null);
    }
  };

  // Pointer Move (Resizing / Moving / Drawing)
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragHandle) return;
    e.stopPropagation();

    const pt = clientToPdfPoint(e.clientX, e.clientY);
    const start = dragStartRef.current;

    if (dragHandle === 'create') {
      setBoxPdf({
        x0: Math.min(start.x, pt.x),
        y0: Math.min(start.y, pt.y),
        x1: Math.max(start.x, pt.x),
        y1: Math.max(start.y, pt.y),
      });
    } else if (dragHandle === 'move' && start.origBox) {
      const dx = pt.x - start.x;
      const dy = pt.y - start.y;
      const boxW = start.origBox.x1 - start.origBox.x0;
      const boxH = start.origBox.y1 - start.origBox.y0;

      let newX0 = Math.max(0, Math.min(pageWidth - boxW, start.origBox.x0 + dx));
      let newY0 = Math.max(0, Math.min(pageHeight - boxH, start.origBox.y0 + dy));

      setBoxPdf({
        x0: newX0,
        y0: newY0,
        x1: newX0 + boxW,
        y1: newY0 + boxH,
      });
    } else if (start.origBox) {
      // Corner handle dragging
      let { x0, y0, x1, y1 } = start.origBox;

      switch (dragHandle) {
        case 'tl':
          x0 = Math.min(pt.x, x1 - 5);
          y0 = Math.min(pt.y, y1 - 5);
          break;
        case 'tr':
          x1 = Math.max(pt.x, x0 + 5);
          y0 = Math.min(pt.y, y1 - 5);
          break;
        case 'bl':
          x0 = Math.min(pt.x, x1 - 5);
          y1 = Math.max(pt.y, y0 + 5);
          break;
        case 'br':
          x1 = Math.max(pt.x, x0 + 5);
          y1 = Math.max(pt.y, y0 + 5);
          break;
      }

      setBoxPdf({ x0, y0, x1, y1 });
    }
  };

  // Pointer Up
  const handlePointerUp = () => {
    if (!dragHandle) return;
    setDragHandle(null);

    // Validate minimum area
    if (boxPdf) {
      const w = Math.abs(boxPdf.x1 - boxPdf.x0);
      const h = Math.abs(boxPdf.y1 - boxPdf.y0);
      if (w * h < 15) {
        // Selection too small, dismiss
        setBoxPdf(null);
      }
    }
  };

  // Handle Text Span Click in Text Mode
  const handleSpanClick = (span: TextSpanItem, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedSpanIds);

    if (newSelected.has(span.id)) {
      newSelected.delete(span.id);
    } else {
      newSelected.add(span.id);
    }

    setSelectedSpanIds(newSelected);

    // Recompute bounding box enclosing all selected spans
    const activeSpans = textSpans.filter((s) => newSelected.has(s.id));
    if (activeSpans.length === 0) {
      setBoxPdf(null);
      setSelectedText('');
      return;
    }

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    activeSpans.forEach((s) => {
      minX = Math.min(minX, s.bbox.x0);
      minY = Math.min(minY, s.bbox.y0);
      maxX = Math.max(maxX, s.bbox.x1);
      maxY = Math.max(maxY, s.bbox.y1);
    });

    setBoxPdf({ x0: minX, y0: minY, x1: maxX, y1: maxY });
    setSelectedText(activeSpans.map((s) => s.text).join(' '));
    setDetectionResult(null);
    setAnalysisError(null);
  };

  // Run Phase C Smart Manual Detection
  const handleAnalyzeSelection = async () => {
    if (!boxPdf) return;

    const currentReqId = ++requestSeqRef.current;
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      // Calculate normalized coordinates [0, 1000] for maximum cross-platform compatibility
      const normX0 = Math.round((boxPdf.x0 / pageWidth) * 1000);
      const normY0 = Math.round((boxPdf.y0 / pageHeight) * 1000);
      const normX1 = Math.round((boxPdf.x1 / pageWidth) * 1000);
      const normY1 = Math.round((boxPdf.y1 / pageHeight) * 1000);

      const result = await api.detections.manualDetect({
        documentId,
        pageIndex,
        selectionType: mode,
        pageWidth,
        pageHeight,
        rawBbox: [boxPdf.x0, boxPdf.y0, boxPdf.x1, boxPdf.y1],
        normalizedBox: [normX0, normY0, normX1, normY1],
        selectedText: mode === 'text' && selectedText ? selectedText : undefined,
      });

      // Discard stale responses if user triggered a new selection
      if (currentReqId !== requestSeqRef.current) return;

      setDetectionResult(result);
      if (onResult) {
        onResult(result);
      }
    } catch (err: any) {
      if (currentReqId !== requestSeqRef.current) return;
      setAnalysisError(err?.message || 'Manual detection analysis failed.');
    } finally {
      if (currentReqId === requestSeqRef.current) {
        setIsAnalyzing(false);
      }
    }
  };

  const handleClear = () => {
    requestSeqRef.current++;
    setBoxPdf(null);
    setSelectedText('');
    setSelectedSpanIds(new Set());
    setDetectionResult(null);
    setAnalysisError(null);
    setIsAnalyzing(false);
  };

  // Compute pixel positions for rendering
  const boxPx = boxPdf
    ? {
        x: Math.round(boxPdf.x0 * scale),
        y: Math.round(boxPdf.y0 * scale),
        w: Math.round((boxPdf.x1 - boxPdf.x0) * scale),
        h: Math.round((boxPdf.y1 - boxPdf.y0) * scale),
      }
    : null;

  return (
    <div
      ref={overlayRef}
      onPointerDown={(e) => handlePointerDown(e, 'create')}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      className="absolute inset-0 z-20 cursor-crosshair select-none touch-none overflow-hidden"
      style={{ width: `${canvasWidth}px`, height: `${canvasHeight}px` }}
    >
      {/* Top Banner: Galaxy AI-inspired Mode Indicator */}
      <div className="absolute top-3 left-3 z-30 flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/85 backdrop-blur-md text-white shadow-xl border border-indigo-500/30 text-xs">
        <Sparkles className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
        <span className="font-semibold tracking-wide bg-gradient-to-r from-blue-300 via-indigo-200 to-purple-300 bg-clip-text text-transparent">
          {mode === 'area' ? 'Area Selection' : 'Text Selection'}
        </span>
        <span className="text-[10px] text-slate-400 border-l border-slate-700 pl-2">
          {mode === 'area' ? 'Drag rectangle over footer' : 'Tap text tokens to highlight'}
        </span>
        <button
          onClick={onClose}
          className="ml-1 p-0.5 hover:bg-white/10 rounded-full transition-colors text-slate-400 hover:text-white"
          title="Exit Smart Select"
        >
          <X className="h-3 w-3" />
        </button>
      </div>

      {/* Text selection mode: Interactive text span tokens */}
      {mode === 'text' && (
        <div className="absolute inset-0 pointer-events-auto">
          {textSpans.map((span) => {
            const isSelected = selectedSpanIds.has(span.id);
            const left = span.bbox.x0 * scale;
            const top = span.bbox.y0 * scale;
            const width = (span.bbox.x1 - span.bbox.x0) * scale;
            const height = (span.bbox.y1 - span.bbox.y0) * scale;

            return (
              <div
                key={span.id}
                onClick={(e) => handleSpanClick(span, e)}
                style={{
                  left: `${left}px`,
                  top: `${top}px`,
                  width: `${width}px`,
                  height: `${height}px`,
                }}
                className={`absolute cursor-pointer transition-all duration-150 rounded ${
                  isSelected
                    ? 'bg-indigo-500/35 border border-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.5)]'
                    : 'hover:bg-indigo-300/20 hover:border hover:border-indigo-300/40'
                }`}
                title={span.text}
              />
            );
          })}
        </div>
      )}

      {/* Area Selection Box & Dimming Backdrop */}
      {boxPx && (
        <div
          style={{
            left: `${boxPx.x}px`,
            top: `${boxPx.y}px`,
            width: `${boxPx.w}px`,
            height: `${boxPx.h}px`,
            // Hardware-accelerated dimming outside selection
            boxShadow: '0 0 0 9999px rgba(15, 23, 42, 0.45)',
          }}
          onPointerDown={(e) => handlePointerDown(e, 'move')}
          className="absolute cursor-move border-2 border-indigo-400 rounded-lg shadow-[0_0_18px_rgba(99,102,241,0.65),inset_0_0_12px_rgba(139,92,246,0.3)] transition-shadow duration-150"
        >
          {/* Subtle animated Galaxy AI border glow */}
          <div className="absolute inset-0 rounded-lg pointer-events-none border border-white/40" />

          {/* Draggable Corner Handles */}
          {/* Top-Left */}
          <div
            onPointerDown={(e) => handlePointerDown(e, 'tl')}
            className="absolute -top-2.5 -left-2.5 w-5 h-5 bg-white rounded-full border-2 border-indigo-600 shadow-md cursor-nwse-resize flex items-center justify-center hover:scale-125 transition-transform"
          >
            <div className="w-1.5 h-1.5 bg-indigo-600 rounded-full" />
          </div>

          {/* Top-Right */}
          <div
            onPointerDown={(e) => handlePointerDown(e, 'tr')}
            className="absolute -top-2.5 -right-2.5 w-5 h-5 bg-white rounded-full border-2 border-indigo-600 shadow-md cursor-nesw-resize flex items-center justify-center hover:scale-125 transition-transform"
          >
            <div className="w-1.5 h-1.5 bg-indigo-600 rounded-full" />
          </div>

          {/* Bottom-Left */}
          <div
            onPointerDown={(e) => handlePointerDown(e, 'bl')}
            className="absolute -bottom-2.5 -left-2.5 w-5 h-5 bg-white rounded-full border-2 border-indigo-600 shadow-md cursor-nesw-resize flex items-center justify-center hover:scale-125 transition-transform"
          >
            <div className="w-1.5 h-1.5 bg-indigo-600 rounded-full" />
          </div>

          {/* Bottom-Right */}
          <div
            onPointerDown={(e) => handlePointerDown(e, 'br')}
            className="absolute -bottom-2.5 -right-2.5 w-5 h-5 bg-white rounded-full border-2 border-indigo-600 shadow-md cursor-nwse-resize flex items-center justify-center hover:scale-125 transition-transform"
          >
            <div className="w-1.5 h-1.5 bg-indigo-600 rounded-full" />
          </div>
        </div>
      )}

      {/* Floating Contextual Action & Results Panel */}
      {boxPx && (
        <div
          onPointerDown={(e) => e.stopPropagation()}
          style={{
            // Smart vertical positioning: above box if space allows, otherwise below
            top: boxPx.y + boxPx.h + 16 > canvasHeight - 200 ? `${Math.max(16, boxPx.y - 190)}px` : `${boxPx.y + boxPx.h + 16}px`,
            left: `${Math.max(16, Math.min(canvasWidth - 360, boxPx.x + boxPx.w / 2 - 180))}px`,
          }}
          className="absolute z-40 w-[360px] max-w-[92vw] rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-indigo-500/30 text-white shadow-2xl p-4 transition-all duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 mb-3">
            <div className="flex items-center gap-2">
              <div className="p-1 rounded-lg bg-indigo-500/20 text-indigo-400">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <span className="text-xs font-bold tracking-wide text-white">
                  Smart Manual Detection
                </span>
                <span className="block text-[10px] text-slate-400">
                  Search Boundary Hint (Phase B Verified)
                </span>
              </div>
            </div>
            <button
              onClick={handleClear}
              className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              title="Clear selection"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Idle / Selection Info */}
          {!detectionResult && !isAnalyzing && !analysisError && (
            <div className="space-y-3">
              <div className="text-xs text-slate-300">
                {mode === 'text' && selectedText ? (
                  <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs font-mono text-indigo-200 line-clamp-2">
                    "{selectedText}"
                  </div>
                ) : (
                  <p className="text-slate-400 text-xs">
                    Target region selected ({Math.round(boxPdf!.x1 - boxPdf!.x0)} × {Math.round(boxPdf!.y1 - boxPdf!.y0)} pt).
                    Pass content to offline verification engine:
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleAnalyzeSelection}
                  className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 transition-all active:scale-[0.98]"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Analyze Selection
                </button>
                <button
                  onClick={handleClear}
                  className="py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs border border-slate-700 transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Loading State */}
          {isAnalyzing && (
            <div className="py-4 flex flex-col items-center justify-center gap-2.5 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
              <span className="text-xs font-semibold text-slate-200">
                Verifying Footer & Identifying Student Fields...
              </span>
              <span className="text-[10px] text-slate-400 max-w-[260px]">
                Checking academic stop words, layout signals, and unlabelled credentials locally.
              </span>
            </div>
          )}

          {/* Error State */}
          {analysisError && (
            <div className="space-y-3">
              <div className="flex items-start gap-2 p-2.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
                <span>{analysisError}</span>
              </div>
              <button
                onClick={handleAnalyzeSelection}
                className="w-full py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200"
              >
                Retry Analysis
              </button>
            </div>
          )}

          {/* Result State */}
          {detectionResult && (
            <div className="space-y-3">
              {/* Status Badge */}
              <div className="flex items-center justify-between">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${
                    detectionResult.footerStatus === 'FOOTER_CONFIRMED'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : detectionResult.footerStatus === 'FOOTER_UNCERTAIN'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                  }`}
                >
                  {detectionResult.footerStatus === 'FOOTER_CONFIRMED' ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : detectionResult.footerStatus === 'FOOTER_UNCERTAIN' ? (
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  {detectionResult.footerStatus.replace('_', ' ')}
                </span>
                <span className="text-[11px] text-slate-400 font-medium">
                  {Math.round(detectionResult.confidence * 100)}% Confidence
                </span>
              </div>

              {/* Summary message */}
              <p className="text-xs text-slate-300 leading-relaxed">
                {detectionResult.summaryMessage}
              </p>

              {/* Detected Student Fields List */}
              {detectionResult.candidates && detectionResult.candidates.length > 0 && (
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Verified Student Credentials:
                  </span>
                  {detectionResult.candidates.map((c) => (
                    <div
                      key={c.id}
                      className="p-2 rounded-xl bg-slate-800/80 border border-slate-700/80 flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wide block">
                          {c.fieldType.replace('_', ' ')}
                        </span>
                        <span className="font-bold text-white">{c.detectedText}</span>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                        {Math.round(c.confidence * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Negative Reasons if Rejected */}
              {detectionResult.negativeReasons && detectionResult.negativeReasons.length > 0 && (
                <div className="p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block">
                    Rejection Reasons:
                  </span>
                  <ul className="list-disc list-inside text-[11px] text-slate-300 space-y-0.5">
                    {detectionResult.negativeReasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Reselect Button */}
              <button
                onClick={handleClear}
                className="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs border border-slate-700 transition-colors flex items-center justify-center gap-1.5"
              >
                <RotateCcw className="h-3 w-3" />
                Select Another Area
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
