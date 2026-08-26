import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Eye,
  Wand2,
  Download,
  Loader2,
  Image as ImageIcon,
  History,
  Lock,
  Sparkles,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Package,
  Split,
  Columns,
  RotateCcw,
  ArrowLeftRight,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Terminal,
  Shirt,
  X,
  Hand,
  Move,
  Maximize,
} from 'lucide-react';

export default function CanvasViewport({
  imageUrl = null,
  beforeImageUrl = null,
  baselineImageUrl = null,
  beforeLabel = 'Baseline',
  afterLabel = 'Regenerated',
  isGenerating = false,
  isExporting = false,
  generationResult = null,
  previousGenerationResult = null,
  activeSeed = 4289102,
  seedMode = 'locked',
  onGenerate,
  onExportBundle,
  onOpenHistory,
  canGenerate = true,
  isInpaintMode = false,
  mode = 'tag',
  wardrobeAssignments = [],
  onDropGarment = null,
  onRemovePin = null,
  onUpdatePinPosition = null,
  isWardrobeMode = false,
}) {
  const [zoom, setZoom] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sliderPos, setSliderPos] = useState(50);
  const [viewMode, setViewMode] = useState('split'); // 'split', 'side_by_side', 'after', 'before'
  const [isPeeking, setIsPeeking] = useState(false);
  const [isPromptExpanded, setIsPromptExpanded] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [compareSource, setCompareSource] = useState('previous'); // 'previous' | 'baseline'
  const [showMaskOverlay, setShowMaskOverlay] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedPinNumber, setSelectedPinNumber] = useState(null);
  const [draggingPinNumber, setDraggingPinNumber] = useState(null);

  const imageContainerRef = useRef(null);
  const viewportBoxRef = useRef(null);
  const panStartRef = useRef({ x: 0, y: 0 });
  const isPanningRef = useRef(false);
  const isSpacePressedRef = useRef(false);
  const zoomRef = useRef(1);
  zoomRef.current = zoom;


  const inpaintMeta = generationResult?.inpaint_metadata || generationResult?.schema_json?.inpaint_metadata;
  const maskUrl = generationResult?.mask_url || generationResult?.mask_image_url || inpaintMeta?.mask_url;
  const maskStats = generationResult?.mask_stats || inpaintMeta?.mask_stats;

  const activeSubmittedPrompt = generationResult?.compiled_prompt || generationResult?.prompt || '';


  const handleCopyPrompt = async () => {
    if (!activeSubmittedPrompt) return;
    try {
      await navigator.clipboard.writeText(activeSubmittedPrompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    } catch (err) {
      console.error('Failed to copy prompt to clipboard', err);
    }
  };

  const getGenerationModeLabel = () => {
    if (!generationResult) return 'Baseline Candidate';
    if (generationResult.is_baseline || generationResult.generation_id?.startsWith('gen_base_')) {
      return 'Baseline Foundation';
    }
    if (generationResult.generation_id?.startsWith('gen_inpaint_') || activeSubmittedPrompt.startsWith('[Inpaint')) {
      return 'Targeted Inpaint';
    }
    if (generationResult.generation_id?.startsWith('gen_iter_')) {
      return 'Fine-Tuned Iteration';
    }
    return 'API Render';
  };

  const hasBaselineOption = Boolean(
    baselineImageUrl &&
    beforeImageUrl &&
    baselineImageUrl !== beforeImageUrl &&
    baselineImageUrl !== imageUrl
  );

  const effectiveBeforeUrl =
    compareSource === 'baseline' && baselineImageUrl
      ? baselineImageUrl
      : beforeImageUrl || baselineImageUrl;

  const effectiveBeforeLabel =
    compareSource === 'baseline' && baselineImageUrl
      ? 'Baseline'
      : beforeLabel;

  const hasComparison = Boolean(
    effectiveBeforeUrl &&
    imageUrl &&
    effectiveBeforeUrl !== imageUrl
  );

  const activeDisplayUrl = isPeeking
    ? effectiveBeforeUrl
    : showMaskOverlay && maskUrl
    ? maskUrl
    : viewMode === 'before' && hasComparison
    ? effectiveBeforeUrl
    : imageUrl;


  const handleDownloadSingle = () => {
    if (!activeDisplayUrl) return;
    const link = document.createElement('a');
    link.href = activeDisplayUrl;
    link.download = `artwork_${generationResult?.generation_id || 'master'}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDragOver = (e) => {
    if (!isWardrobeMode) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    if (!isWardrobeMode) return;
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    if (!isWardrobeMode) return;
    e.preventDefault();
    setIsDragOver(false);
    const dataStr = e.dataTransfer.getData('application/json');
    if (!dataStr) return;
    try {
      const item = JSON.parse(dataStr);
      const imgElem = imageContainerRef.current;
      if (!imgElem) return;
      const rect = imgElem.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      onDropGarment?.(item, { x, y });
    } catch (err) {
      console.error('Failed to parse dropped garment', err);
    }
  };

  const clampPan = useCallback((x, y, currentZoom = zoom) => {
    if (!viewportBoxRef.current) return { x, y };
    const viewportRect = viewportBoxRef.current.getBoundingClientRect();
    const maxPanX = Math.max(80, (viewportRect.width * Math.max(0, currentZoom - 0.7)) / 2 + 120);
    const maxPanY = Math.max(80, (viewportRect.height * Math.max(0, currentZoom - 0.7)) / 2 + 120);
    return {
      x: Math.max(-maxPanX, Math.min(maxPanX, x)),
      y: Math.max(-maxPanY, Math.min(maxPanY, y)),
    };
  }, [zoom]);

  // Spacebar Hand Tool & Keyboard Deletion Listeners
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = e.target?.tagName?.toLowerCase();
      const isTyping = tag === 'input' || tag === 'textarea' || e.target?.isContentEditable;
      if (isTyping) return;

      if (e.code === 'Space' || e.key === ' ') {
        e.preventDefault();
        setIsSpacePressed(true);
        isSpacePressedRef.current = true;
      }

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedPinNumber !== null) {
        e.preventDefault();
        onRemovePin?.(selectedPinNumber);
        setSelectedPinNumber(null);
      }
    };

    const handleKeyUp = (e) => {
      if (e.code === 'Space' || e.key === ' ') {
        setIsSpacePressed(false);
        isSpacePressedRef.current = false;
        setIsPanning(false);
        isPanningRef.current = false;
      }
    };

    const handleWindowBlur = () => {
      setIsSpacePressed(false);
      isSpacePressedRef.current = false;
      setIsPanning(false);
      isPanningRef.current = false;
      setDraggingPinNumber(null);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleWindowBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleWindowBlur);
    };
  }, [selectedPinNumber, onRemovePin]);

  const handleViewportMouseDown = (e) => {
    if (isSpacePressedRef.current || e.button === 1) {
      e.preventDefault();
      setIsPanning(true);
      isPanningRef.current = true;
      panStartRef.current = {
        x: e.clientX - panOffset.x,
        y: e.clientY - panOffset.y,
      };
    }
  };

  const handleViewportMouseMove = (e) => {
    if (isPanningRef.current) {
      e.preventDefault();
      const rawX = e.clientX - panStartRef.current.x;
      const rawY = e.clientY - panStartRef.current.y;
      const clamped = clampPan(rawX, rawY, zoomRef.current);
      setPanOffset(clamped);
    } else if (draggingPinNumber !== null && imageContainerRef.current) {
      e.preventDefault();
      const rect = imageContainerRef.current.getBoundingClientRect();
      const x = Math.max(0.02, Math.min(0.98, (e.clientX - rect.left) / rect.width));
      const y = Math.max(0.02, Math.min(0.98, (e.clientY - rect.top) / rect.height));
      onUpdatePinPosition?.(draggingPinNumber, { x, y });
    }
  };

  const handleViewportMouseUp = () => {
    if (isPanningRef.current) {
      setIsPanning(false);
      isPanningRef.current = false;
    }
    if (draggingPinNumber !== null) {
      setDraggingPinNumber(null);
    }
  };

  const handleResetFit = () => {
    setZoom(1);
    setPanOffset({ x: 0, y: 0 });
  };

  return (
    <div className="canvas-viewport-panel">

      {/* Viewport Header */}
      <div className="viewport-header">
        <div className="viewport-title-group">
          <Eye size={18} className="text-accent" />
          <span className="viewport-title">4K Master Canvas Viewport</span>
        </div>

        {/* Center: Before / After Comparison Toolbar */}
        {hasComparison && (
          <div className="viewport-comparison-toolbar">
            <button
              type="button"
              className={`viewport-compare-tab ${viewMode === 'split' ? 'active' : ''}`}
              onClick={() => setViewMode('split')}
              title="Split-Slider Comparison"
            >
              <Split size={13} />
              <span>Split</span>
            </button>

            <button
              type="button"
              className={`viewport-compare-tab ${viewMode === 'side_by_side' ? 'active' : ''}`}
              onClick={() => setViewMode('side_by_side')}
              title="Side-by-Side Comparison"
            >
              <Columns size={13} />
              <span>Side-by-Side</span>
            </button>

            <button
              type="button"
              className={`viewport-compare-tab ${viewMode === 'after' ? 'active' : ''}`}
              onClick={() => setViewMode('after')}
              title="View Current / Regenerated Result"
            >
              <Sparkles size={13} />
              <span>After</span>
            </button>

            <button
              type="button"
              className={`viewport-compare-tab ${viewMode === 'before' ? 'active' : ''}`}
              onClick={() => setViewMode('before')}
              title={`View ${effectiveBeforeLabel} Reference`}
            >
              <RotateCcw size={13} />
              <span>Before ({effectiveBeforeLabel})</span>
            </button>

            {/* Quick Hold to Compare Button */}
            <button
              type="button"
              className={`viewport-peek-btn ${isPeeking ? 'active' : ''}`}
              onMouseDown={() => setIsPeeking(true)}
              onMouseUp={() => setIsPeeking(false)}
              onMouseLeave={() => setIsPeeking(false)}
              onTouchStart={() => setIsPeeking(true)}
              onTouchEnd={() => setIsPeeking(false)}
              title={`Press & hold to momentarily peek at the ${effectiveBeforeLabel.toLowerCase()}`}
            >
              <Eye size={13} />
              <span>Hold: Peek Before</span>
            </button>

            {/* Reference Target Switcher if multiple references exist */}
            {hasBaselineOption && (
              <div
                className="viewport-compare-source-toggle"
                style={{
                  display: 'inline-flex',
                  marginLeft: '4px',
                  background: 'rgba(0,0,0,0.3)',
                  padding: '2px',
                  borderRadius: 'var(--radius-pill)',
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <button
                  type="button"
                  className={`viewport-compare-tab ${compareSource === 'previous' ? 'active' : ''}`}
                  onClick={() => setCompareSource('previous')}
                  style={{ padding: '2px 7px', fontSize: '0.66rem' }}
                  title="Compare with immediate previous iteration"
                >
                  Prev
                </button>
                <button
                  type="button"
                  className={`viewport-compare-tab ${compareSource === 'baseline' ? 'active' : ''}`}
                  onClick={() => setCompareSource('baseline')}
                  style={{ padding: '2px 7px', fontSize: '0.66rem' }}
                  title="Compare with original baseline photo"
                >
                  Base
                </button>
              </div>
            )}
          </div>
        )}

        <div className="viewport-header-actions">
          {onOpenHistory && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onOpenHistory}
              title="Open Generation Lineage & History"
            >
              <History size={14} />
              <span>History</span>
            </button>
          )}

          {generationResult && (
            <span className="viewport-meta-badge">
              ID: {generationResult.generation_id} | {generationResult.resolution?.width}×{generationResult.resolution?.height}
            </span>
          )}
        </div>
      </div>

      {/* Main Image Rendering Area */}
      <div
        ref={viewportBoxRef}
        className={`viewport-image-box ${isFullscreen ? 'viewport-fullscreen' : ''} ${isSpacePressed ? 'hand-cursor-active' : ''} ${isPanning ? 'is-panning-active' : ''}`}
        onMouseDown={handleViewportMouseDown}
        onMouseMove={handleViewportMouseMove}
        onMouseUp={handleViewportMouseUp}
        onMouseLeave={handleViewportMouseUp}
      >
        {hasComparison && viewMode === 'split' && !isPeeking ? (
          /* Split Slider Viewport */
          <div
            className="split-slider-viewport image-zoom-container"
            style={{
              width: '100%',
              height: '100%',
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isPanning ? 'none' : 'transform 0.15s ease-out',
            }}
          >
            {/* Version A Background: Before / Baseline */}
            <img src={effectiveBeforeUrl} alt={`Before: ${effectiveBeforeLabel}`} className="split-image-layer layer-a" />
            <span className="comparison-badge badge-before">BEFORE ({effectiveBeforeLabel})</span>

            {/* Version B Clipped Layer: After / Regenerated */}
            <div
              className="split-image-layer layer-b"
              style={{
                clipPath: `inset(0 0 0 ${sliderPos}%)`,
              }}
            >
              <img src={imageUrl} alt={`After: ${afterLabel}`} className="split-image-inner" />
            </div>
            <span className="comparison-badge badge-after">AFTER ({afterLabel})</span>

            {/* Draggable Divider Line */}
            <div className="split-divider-line" style={{ left: `${sliderPos}%` }}>
              <div className="split-handle">
                <ArrowLeftRight size={12} />
              </div>
            </div>

            {/* Range Input Scrubbing Overlay */}
            <input
              type="range"
              min="0"
              max="100"
              value={sliderPos}
              onChange={(e) => setSliderPos(Number(e.target.value))}
              className="split-range-input"
              aria-label="Before and after comparison slider"
            />
          </div>
        ) : hasComparison && viewMode === 'side_by_side' && !isPeeking ? (
          /* Side-by-Side Dual Viewport */
          <div
            className="side-by-side-grid"
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isPanning ? 'none' : 'transform 0.15s ease-out',
            }}
          >
            <div className="side-by-side-panel">
              <span className="comparison-badge badge-before">BEFORE ({effectiveBeforeLabel})</span>
              <img src={effectiveBeforeUrl} alt={`Before: ${effectiveBeforeLabel}`} className="side-by-side-image" />
            </div>
            <div className="side-by-side-panel">
              <span className="comparison-badge badge-after">AFTER ({afterLabel})</span>
              <img src={imageUrl} alt={`After: ${afterLabel}`} className="side-by-side-image" />
            </div>
          </div>
        ) : activeDisplayUrl ? (
          /* Single Image View (or Peek Before active) */
          <div
            ref={imageContainerRef}
            className={`image-zoom-container ${isWardrobeMode ? 'is-wardrobe-drop-target' : ''} ${isDragOver ? 'is-drag-active' : ''}`}
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isPanning || draggingPinNumber !== null ? 'none' : 'transform 0.15s ease-out',
              position: 'relative',
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {isPeeking && (
              <span className="comparison-badge badge-peek">PEEKING {effectiveBeforeLabel.toUpperCase()}</span>
            )}
            {!isPeeking && hasComparison && viewMode === 'before' && (
              <span className="comparison-badge badge-before">BEFORE ({effectiveBeforeLabel})</span>
            )}
            {!isPeeking && hasComparison && viewMode === 'after' && (
              <span className="comparison-badge badge-after">AFTER ({afterLabel})</span>
            )}
            <img
              src={activeDisplayUrl}
              alt={isPeeking ? 'Reference Photo' : 'Master Rendered Artwork'}
              className="rendered-canvas-image"
            />

            {/* Wardrobe Drop Hint Overlay */}
            {isWardrobeMode && isDragOver && (
              <div className="wardrobe-drop-hint-overlay">
                <Shirt size={28} className="animate-bounce text-accent" />
                <span className="drop-hint-title">Drop to Pin Garment</span>
                <span className="drop-hint-subtitle">Pin will assign this garment to this body location</span>
              </div>
            )}

            {/* Wardrobe Numbered Pins Overlay with Drag & Delete */}
            {isWardrobeMode && wardrobeAssignments.map((asgn) => {
              const posX = (asgn.drop_position?.x ?? 0.5) * 100;
              const posY = (asgn.drop_position?.y ?? 0.5) * 100;
              const isSelected = selectedPinNumber === asgn.pin_number;
              const isDragging = draggingPinNumber === asgn.pin_number;

              return (
                <div
                  key={asgn.pin_number}
                  className={`wardrobe-pin-marker ${isSelected ? 'selected' : ''} ${isDragging ? 'is-dragging' : ''}`}
                  style={{ left: `${posX}%`, top: `${posY}%` }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedPinNumber(asgn.pin_number);
                  }}
                  onMouseDown={(e) => {
                    // Left click to start dragging
                    if (e.button === 0) {
                      e.stopPropagation();
                      setSelectedPinNumber(asgn.pin_number);
                      setDraggingPinNumber(asgn.pin_number);
                    }
                  }}
                  title={`Pin #${asgn.pin_number}: ${asgn.item_label || 'Garment'} (Drag to move, click X or press Backspace to remove)`}
                  role="button"
                  tabIndex={0}
                >
                  <div className="pin-pulse-ring" />
                  <div className="pin-circle-badge">
                    <Move size={9} className="pin-drag-handle-icon" />
                    <span>{asgn.pin_number}</span>
                  </div>
                  <div className="pin-tooltip-popover">
                    <div className="pin-info-row">
                      <span className="pin-tooltip-label">{asgn.item_label || 'Garment'}</span>
                      <span className="pin-coords-badge">{Math.round(posX)}%, {Math.round(posY)}%</span>
                    </div>
                    <button
                      type="button"
                      className="pin-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemovePin?.(asgn.pin_number);
                        if (selectedPinNumber === asgn.pin_number) {
                          setSelectedPinNumber(null);
                        }
                      }}
                      title="Remove pin"
                      aria-label={`Remove pin ${asgn.pin_number}`}
                    >
                      <X size={11} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="viewport-empty-placeholder">
            <ImageIcon size={48} className="placeholder-icon" />
            <div className="placeholder-title">4K Master Artwork will render here</div>
            <div className="placeholder-subtitle">
              Select a baseline and trigger non-destructive fine-tuning to render iterations.
            </div>
          </div>
        )}

        {/* Loading Overlay */}
        {isGenerating && (
          <div className="viewport-loading-overlay">
            <Loader2 className="spin-animation" size={44} />
            <div className="loading-title">
              {isInpaintMode ? 'Applying Precision Inpaint Edit...' : 'Generating Master Artwork...'}
            </div>
            <div className="loading-subtitle">
              {isInpaintMode
                ? 'Synthesizing targeted adjustment and blending boundaries'
                : `Applying multimodal reference conditioning under locked seed #${activeSeed}`}
            </div>
          </div>
        )}

        {/* Viewport Overlay Controls */}
        {(imageUrl || beforeImageUrl) && (
          <div className="viewport-overlay-controls">
            <button
              type="button"
              className={`viewport-control-btn ${zoom === 1 && panOffset.x === 0 && panOffset.y === 0 ? 'active' : ''}`}
              onClick={handleResetFit}
              title="Fit to Width / Reset View"
            >
              <RotateCcw size={13} />
              <span className="viewport-fit-label">Fit</span>
            </button>
            <button
              type="button"
              className="viewport-control-btn"
              onClick={() => setZoom((z) => Math.min(Number((z + 0.25).toFixed(2)), 3))}
              title="Zoom In"
            >
              <ZoomIn size={15} />
            </button>
            <span className="zoom-percentage">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              className="viewport-control-btn"
              onClick={() => setZoom((z) => Math.max(Number((z - 0.25).toFixed(2)), 0.5))}
              title="Zoom Out"
            >
              <ZoomOut size={15} />
            </button>
            <button
              type="button"
              className={`viewport-control-btn ${isSpacePressed ? 'active' : ''}`}
              onClick={() => {
                setIsSpacePressed(!isSpacePressed);
                isSpacePressedRef.current = !isSpacePressed;
              }}
              title="Hold [Spacebar] + Drag to Pan View"
            >
              <Hand size={15} />
            </button>
            <button
              type="button"
              className="viewport-control-btn"
              onClick={() => setIsFullscreen(!isFullscreen)}
              title="Toggle Fullscreen View"
            >
              <Maximize2 size={15} />
            </button>
          </div>
        )}
      </div>

      {/* Full Prompt Submitted to API Inspector */}
      {activeSubmittedPrompt && (
        <div className="viewport-prompt-panel">
          <div className="viewport-prompt-header">
            <div className="viewport-prompt-title-group">
              <Terminal size={14} className="text-accent" />
              <span className="viewport-prompt-title">Full Prompt Submitted to API</span>
              <span className="viewport-prompt-mode-tag">
                {getGenerationModeLabel()}
              </span>
              {generationResult?.seed && (
                <span className="viewport-prompt-seed-pill">
                  Seed #{generationResult.seed}
                </span>
              )}
              {maskStats?.coverage_percentage !== undefined && (
                <span
                  className="viewport-prompt-seed-pill inpaint-mask-pill"
                  title={`Targeted inpaint mask area: ${maskStats.coverage_percentage}% of canvas (bbox: ${maskStats.bounding_box?.width || 0}×${maskStats.bounding_box?.height || 0}px)`}
                >
                  Mask: {maskStats.coverage_percentage}%
                </span>
              )}
            </div>

            <div className="viewport-prompt-actions">
              {maskUrl && (
                <button
                  type="button"
                  className={`btn-prompt-action ${showMaskOverlay ? 'btn-prompt-action-active' : ''}`}
                  onClick={() => setShowMaskOverlay(!showMaskOverlay)}
                  title={showMaskOverlay ? "Return to rendered artwork" : "Inspect targeted inpaint mask map"}
                >
                  <Eye size={12} />
                  <span>{showMaskOverlay ? "Artwork" : "Mask Map"}</span>
                </button>
              )}

              <button
                type="button"
                className="btn-prompt-action"
                onClick={handleCopyPrompt}
                title="Copy Full Prompt to Clipboard"
              >

                {copiedPrompt ? (
                  <>
                    <Check size={12} className="text-success" />
                    <span className="text-success">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Copy</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-prompt-action"
                onClick={() => setIsPromptExpanded(!isPromptExpanded)}
                title={isPromptExpanded ? "Collapse prompt view" : "Expand full prompt view"}
              >
                {isPromptExpanded ? (
                  <>
                    <ChevronUp size={12} />
                    <span>Collapse</span>
                  </>
                ) : (
                  <>
                    <ChevronDown size={12} />
                    <span>Expand</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <div
            className={`viewport-prompt-content ${isPromptExpanded ? 'expanded' : 'collapsed'}`}
          >
            {activeSubmittedPrompt}
          </div>
        </div>
      )}

      {/* Action Footer Bar */}
      <div className="viewport-actions-footer">
        {/* Seed Info Badge */}
        <div className="seed-status-bar">
          <div className="seed-indicator">
            <Lock size={13} className="text-accent" />
            <span>Seed: #{activeSeed} ({seedMode})</span>
          </div>
          {mode === 'tag' && <span className="shortcut-hint">Shortcut: ⌘ + Enter</span>}
          {mode === 'refinement' && <span className="shortcut-hint">Prompt in Refinement Thread</span>}
          {mode === 'canvas' && <span className="shortcut-hint">Live Inpaint Preview</span>}
        </div>

        <div className="action-buttons-row">
          {mode === 'tag' && (
            <button
              type="button"
              className="btn-primary flex-1"
              disabled={!canGenerate || isGenerating}
              onClick={onGenerate}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="spin-animation" size={16} />
                  <span>Fine-Tuning Artwork...</span>
                </>
              ) : (
                <>
                  <Wand2 size={16} />
                  <span>Re-Generate Fine-Tuning</span>
                </>
              )}
            </button>
          )}

          {activeDisplayUrl && (
            <>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleDownloadSingle}
                title="Download single high-res PNG"
              >
                <Download size={15} />
                <span>Single PNG</span>
              </button>

              <button
                type="button"
                className="btn-success"
                disabled={!generationResult?.generation_id || isGenerating || isExporting}
                onClick={() => generationResult?.generation_id && onExportBundle(generationResult.generation_id)}
                title="Export 5-Preset ZIP Archive"
              >
                {isExporting ? (
                  <>
                    <Loader2 className="spin-animation" size={15} />
                    <span>Bundling...</span>
                  </>
                ) : (
                  <>
                    <Package size={15} />
                    <span>Download 5-Preset ZIP</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

