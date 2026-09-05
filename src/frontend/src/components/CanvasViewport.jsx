import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Eye,
  Wand2,
  Loader2,
  Image as ImageIcon,
  History,
  Lock,
  Sparkles,
  Maximize2,
  ZoomIn,
  ZoomOut,
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
  Box,
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
  generationResult = null,
  previousGenerationResult = null,
  activeSeed = 4289102,
  seedMode = 'locked',
  onGenerate,
  onOpenHistory,
  canGenerate = true,
  isInpaintMode = false,
  mode = 'tag',
  wardrobeAssignments = [],
  onDropGarment = null,
  onRemovePin = null,
  onUpdatePinPosition = null,
  isWardrobeMode = false,
  isPropsMode = false,
  propAssignments = [],
  onDropProp = null,
  onUpdatePropBox = null,
  onRemovePropAssignment = null,
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
  const [selectedPropPin, setSelectedPropPin] = useState(null);
  const [propDragStart, setPropDragStart] = useState(null);
  const [resizingPropCorner, setResizingPropCorner] = useState(null);

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

  const handleDragOver = (e) => {
    if (!isWardrobeMode && !isPropsMode) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    if (!isWardrobeMode && !isPropsMode) return;
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    if (!isWardrobeMode && !isPropsMode) return;
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
      if (item.isProp || isPropsMode) {
        onDropProp?.(item, { x, y });
      } else if (isWardrobeMode) {
        onDropGarment?.(item, { x, y });
      }
    } catch (err) {
      console.error('Failed to parse dropped item', err);
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

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedPropPin !== null) {
        e.preventDefault();
        onRemovePropAssignment?.(selectedPropPin);
        setSelectedPropPin(null);
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
  }, [selectedPinNumber, onRemovePin, selectedPropPin, onRemovePropAssignment]);

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
    } else if (resizingPropCorner && imageContainerRef.current) {
      e.preventDefault();
      const { pinNumber, corner, startBox, startMouse, aspectRatio: boxAspect } = resizingPropCorner;
      const dx = (e.clientX - startMouse.x) / startMouse.rectWidth;
      const dy = (e.clientY - startMouse.y) / startMouse.rectHeight;
      const isFreeform = e.shiftKey;

      let newXmin = startBox.xmin;
      let newXmax = startBox.xmax;
      let newYmin = startBox.ymin;
      let newYmax = startBox.ymax;

      if (corner === 'se') {
        newXmax = Math.max(startBox.xmin + 0.05, Math.min(1.0, startBox.xmax + dx));
        if (!isFreeform && boxAspect) {
          const newW = newXmax - startBox.xmin;
          newYmax = Math.max(startBox.ymin + 0.05, Math.min(1.0, startBox.ymin + newW / boxAspect));
        } else {
          newYmax = Math.max(startBox.ymin + 0.05, Math.min(1.0, startBox.ymax + dy));
        }
      } else if (corner === 'sw') {
        newXmin = Math.max(0.0, Math.min(startBox.xmax - 0.05, startBox.xmin + dx));
        if (!isFreeform && boxAspect) {
          const newW = startBox.xmax - newXmin;
          newYmax = Math.max(startBox.ymin + 0.05, Math.min(1.0, startBox.ymin + newW / boxAspect));
        } else {
          newYmax = Math.max(startBox.ymin + 0.05, Math.min(1.0, startBox.ymax + dy));
        }
      } else if (corner === 'ne') {
        newXmax = Math.max(startBox.xmin + 0.05, Math.min(1.0, startBox.xmax + dx));
        if (!isFreeform && boxAspect) {
          const newW = newXmax - startBox.xmin;
          newYmin = Math.max(0.0, Math.min(startBox.ymax - 0.05, startBox.ymax - newW / boxAspect));
        } else {
          newYmin = Math.max(0.0, Math.min(startBox.ymax - 0.05, startBox.ymin + dy));
        }
      } else if (corner === 'nw') {
        newXmin = Math.max(0.0, Math.min(startBox.xmax - 0.05, startBox.xmin + dx));
        if (!isFreeform && boxAspect) {
          const newW = startBox.xmax - newXmin;
          newYmin = Math.max(0.0, Math.min(startBox.ymax - 0.05, startBox.ymax - newW / boxAspect));
        } else {
          newYmin = Math.max(0.0, Math.min(startBox.ymax - 0.05, startBox.ymin + dy));
        }
      }
      onUpdatePropBox?.(pinNumber, { xmin: newXmin, xmax: newXmax, ymin: newYmin, ymax: newYmax });
    } else if (propDragStart && imageContainerRef.current) {
      e.preventDefault();
      const { pinNumber, startBox, startMouse } = propDragStart;
      const dx = (e.clientX - startMouse.x) / startMouse.rectWidth;
      const dy = (e.clientY - startMouse.y) / startMouse.rectHeight;
      const w = startBox.xmax - startBox.xmin;
      const h = startBox.ymax - startBox.ymin;
      const newXmin = Math.max(0, Math.min(1 - w, startBox.xmin + dx));
      const newYmin = Math.max(0, Math.min(1 - h, startBox.ymin + dy));
      onUpdatePropBox?.(pinNumber, { xmin: newXmin, xmax: newXmin + w, ymin: newYmin, ymax: newYmin + h });
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
    if (resizingPropCorner !== null) {
      setResizingPropCorner(null);
    }
    if (propDragStart !== null) {
      setPropDragStart(null);
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
              <div className="viewport-compare-source-toggle">
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
            className={`image-zoom-container ${isWardrobeMode || isPropsMode ? 'is-wardrobe-drop-target' : ''} ${isDragOver ? 'is-drag-active' : ''}`}
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isPanning || draggingPinNumber !== null || resizingPropCorner !== null || propDragStart !== null ? 'none' : 'transform 0.15s ease-out',
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

            {/* Props Drop Hint Overlay */}
            {isPropsMode && isDragOver && (
              <div className="wardrobe-drop-hint-overlay">
                <Box size={28} className="animate-bounce text-accent" />
                <span className="drop-hint-title">Drop to Place Prop</span>
                <span className="drop-hint-subtitle">Creates a resizable bounding box for object placement</span>
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

            {/* Props Resizable Bounding Boxes Overlay */}
            {isPropsMode && propAssignments.map((asgn) => {
              const box = asgn.bounding_box || { xmin: 0.35, xmax: 0.65, ymin: 0.35, ymax: 0.65 };
              const isSelected = selectedPropPin === asgn.pin_number;
              const isDraggingBox = propDragStart?.pinNumber === asgn.pin_number;

              return (
                <div
                  key={asgn.pin_number}
                  className={`prop-bounding-box ${isSelected ? 'selected' : ''} ${isDraggingBox ? 'is-dragging' : ''}`}
                  style={{
                    left: `${box.xmin * 100}%`,
                    top: `${box.ymin * 100}%`,
                    width: `${Math.max(0.01, box.xmax - box.xmin) * 100}%`,
                    height: `${Math.max(0.01, box.ymax - box.ymin) * 100}%`,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedPropPin(asgn.pin_number);
                  }}
                  onMouseDown={(e) => {
                    if (e.button === 0 && !e.target.classList.contains('prop-resize-handle') && !e.target.closest('.prop-box-close-btn')) {
                      e.stopPropagation();
                      setSelectedPropPin(asgn.pin_number);
                      if (imageContainerRef.current) {
                        const rect = imageContainerRef.current.getBoundingClientRect();
                        setPropDragStart({
                          pinNumber: asgn.pin_number,
                          startBox: { ...box },
                          startMouse: { x: e.clientX, y: e.clientY, rectWidth: rect.width, rectHeight: rect.height },
                        });
                      }
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  title={`Prop #${asgn.pin_number}: ${asgn.item_label || 'Prop'} (Drag to reposition, corner handles to resize, Delete to remove)`}
                >
                  {/* Bounding Box Header Badge */}
                  <div className="prop-box-header">
                    <div className="prop-box-title">
                      <span className="prop-box-pin">#{asgn.pin_number}</span>
                      <span className="prop-box-label">{asgn.item_label || 'Prop'}</span>
                      <span className="prop-box-scale-pill">{asgn.scale_preset || 'medium'}</span>
                    </div>
                    <button
                      type="button"
                      className="prop-box-close-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemovePropAssignment?.(asgn.pin_number);
                        if (selectedPropPin === asgn.pin_number) {
                          setSelectedPropPin(null);
                        }
                      }}
                      title="Remove prop"
                      aria-label={`Remove prop ${asgn.pin_number}`}
                    >
                      <X size={10} />
                    </button>
                  </div>

                  {/* 4 Corner Resize Handles */}
                  {['nw', 'ne', 'se', 'sw'].map((corner) => (
                    <div
                      key={corner}
                      className={`prop-resize-handle handle-${corner}`}
                      onMouseDown={(e) => {
                        if (e.button === 0) {
                          e.stopPropagation();
                          setSelectedPropPin(asgn.pin_number);
                          if (imageContainerRef.current) {
                            const rect = imageContainerRef.current.getBoundingClientRect();
                            setResizingPropCorner({
                              pinNumber: asgn.pin_number,
                              corner,
                              startBox: { ...box },
                              startMouse: { x: e.clientX, y: e.clientY, rectWidth: rect.width, rectHeight: rect.height },
                              aspectRatio: (box.xmax - box.xmin) / Math.max(0.001, box.ymax - box.ymin),
                            });
                          }
                        }
                      }}
                      title={`Drag to resize (${corner.toUpperCase()}). Hold Shift for freeform.`}
                    />
                  ))}
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

        {mode === 'tag' && (
          <div className="action-buttons-row">
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
          </div>
        )}
      </div>
    </div>
  );
}

