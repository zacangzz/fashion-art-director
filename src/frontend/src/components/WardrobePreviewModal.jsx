import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Sparkles,
  Layers,
  Trash2,
  Tag,
  Palette,
  FileText,
  Image as ImageIcon,
  Check,
  Split,
  Eye,
  Sliders,
  ShieldCheck,
  DollarSign,
} from 'lucide-react';

const CATEGORY_COLORS = {
  outerwear: '#f59e0b',
  tops: '#3b82f6',
  bottoms: '#10b981',
  footwear: '#8b5cf6',
  accessories: '#ec4899',
};

export default function WardrobePreviewModal({
  isOpen = false,
  onClose,
  items = [],
  initialItemId = null,
  onAddAssignment,
  onDeleteItem,
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [viewMode, setViewMode] = useState('hd'); // 'hd', 'crop', 'split', 'source'
  const [splitPos, setSplitPos] = useState(50);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [copiedText, setCopiedText] = useState(false);

  const containerRef = useRef(null);

  // Sync index when initialItemId or items change
  useEffect(() => {
    if (initialItemId && items.length > 0) {
      const idx = items.findIndex((it) => it.id === initialItemId);
      if (idx !== -1) {
        setCurrentIndex(idx);
      }
    }
  }, [initialItemId, items]);

  // Reset zoom & pan when switching items
  useEffect(() => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  }, [currentIndex]);

  const currentItem = items[currentIndex] || null;

  const isUpscaled = currentItem?.is_upscaled || currentItem?.upscale_status === 'completed';
  const hasUpscaledImage = Boolean(currentItem?.upscaled_image_url);
  const hasSourceImage = Boolean(currentItem?.source_image_url);

  // Default viewMode logic
  useEffect(() => {
    if (hasUpscaledImage) {
      setViewMode('hd');
    } else {
      setViewMode('crop');
    }
  }, [currentIndex, hasUpscaledImage]);

  const handlePrev = useCallback(() => {
    if (items.length <= 1) return;
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : items.length - 1));
  }, [items.length]);

  const handleNext = useCallback(() => {
    if (items.length <= 1) return;
    setCurrentIndex((prev) => (prev < items.length - 1 ? prev + 1 : 0));
  }, [items.length]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      } else if (e.key === 'ArrowLeft') {
        handlePrev();
      } else if (e.key === 'ArrowRight') {
        handleNext();
      } else if (e.key === '+' || e.key === '=') {
        setZoomLevel((prev) => Math.min(prev + 0.25, 4));
      } else if (e.key === '-' || e.key === '_') {
        setZoomLevel((prev) => Math.max(prev - 0.25, 0.5));
      } else if (e.key === '0') {
        setZoomLevel(1);
        setPanOffset({ x: 0, y: 0 });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, handlePrev, handleNext]);

  // Pan interaction
  const handleMouseDown = (e) => {
    if (zoomLevel <= 1) return;
    setIsPanning(true);
    setPanStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e) => {
    if (!isPanning || zoomLevel <= 1) return;
    setPanOffset({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY * -0.005;
      setZoomLevel((prev) => Math.min(Math.max(prev + delta, 0.5), 4));
    }
  };

  const handleCopyText = (text) => {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  if (!isOpen || !currentItem) return null;

  const catColor = CATEGORY_COLORS[currentItem.category] || CATEGORY_COLORS.tops;
  const hdImageUrl = currentItem.upscaled_image_url || currentItem.image_url;
  const cropImageUrl = currentItem.image_url;
  const sourceImageUrl = currentItem.source_image_url;
  const details = currentItem.extracted_details || {};

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="garment-modal-title"
    >
      <div
        className="wardrobe-preview-modal-container"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="wardrobe-preview-header">
          <div className="wardrobe-preview-title-group">
            <div className="wardrobe-preview-badge">
              <Eye size={16} className="text-accent" />
              <span>Garment Quality Inspector</span>
            </div>
            <span
              className="garment-cat-pill"
              style={{ color: catColor, borderColor: `${catColor}40`, backgroundColor: `${catColor}15` }}
            >
              {currentItem.category || 'tops'}
            </span>
            {isUpscaled ? (
              <span className="garment-preview-hd-pill">
                <Sparkles size={11} />
                <span>4K Ultra-HD Enhanced</span>
              </span>
            ) : (
              <span className="garment-preview-raw-pill">
                <span>Original Crop</span>
              </span>
            )}
            {Number(currentItem.cost_usd || 0) > 0 && (
              <span className="garment-preview-cost-pill" title={`API Generation Cost: $${Number(currentItem.cost_usd).toFixed(4)} (${currentItem.tokens || 0} tokens)`}>
                <DollarSign size={11} />
                <span>${Number(currentItem.cost_usd).toFixed(4)}</span>
              </span>
            )}
          </div>

          <div className="wardrobe-preview-nav-actions">
            {items.length > 1 && (
              <div className="wardrobe-preview-pagination">
                <button
                  type="button"
                  className="btn-icon-subtle"
                  onClick={handlePrev}
                  title="Previous garment (Arrow Left)"
                  aria-label="Previous garment"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="pagination-text">
                  {currentIndex + 1} / {items.length}
                </span>
                <button
                  type="button"
                  className="btn-icon-subtle"
                  onClick={handleNext}
                  title="Next garment (Arrow Right)"
                  aria-label="Next garment"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            )}

            <button
              type="button"
              className="modal-close-btn"
              onClick={onClose}
              title="Close preview (Esc)"
              aria-label="Close modal"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Main Body */}
        <div className="wardrobe-preview-body">
          {/* Left Viewport / Image Canvas */}
          <div className="wardrobe-preview-viewport-section">
            {/* View Mode Bar */}
            <div className="preview-viewmode-bar">
              <div className="viewmode-toggle-group">
                {hasUpscaledImage && (
                  <button
                    type="button"
                    className={`viewmode-btn ${viewMode === 'hd' ? 'active' : ''}`}
                    onClick={() => setViewMode('hd')}
                    title="View AI-upscaled high-definition garment"
                  >
                    <Sparkles size={13} />
                    <span>HD Enhanced</span>
                  </button>
                )}
                <button
                  type="button"
                  className={`viewmode-btn ${viewMode === 'crop' ? 'active' : ''}`}
                  onClick={() => setViewMode('crop')}
                  title="View original bounding box crop"
                >
                  <ImageIcon size={13} />
                  <span>Original Crop</span>
                </button>
                {hasUpscaledImage && (
                  <button
                    type="button"
                    className={`viewmode-btn ${viewMode === 'split' ? 'active' : ''}`}
                    onClick={() => setViewMode('split')}
                    title="Interactive split-slider comparison between HD and Original"
                  >
                    <Split size={13} />
                    <span>Split Compare</span>
                  </button>
                )}
                {hasSourceImage && (
                  <button
                    type="button"
                    className={`viewmode-btn ${viewMode === 'source' ? 'active' : ''}`}
                    onClick={() => setViewMode('source')}
                    title="View garment highlighted on full source lookbook sheet"
                  >
                    <Sliders size={13} />
                    <span>Source Sheet</span>
                  </button>
                )}
              </div>

              {/* Zoom Controls */}
              <div className="preview-zoom-controls">
                <button
                  type="button"
                  className="btn-zoom"
                  onClick={() => setZoomLevel((prev) => Math.max(prev - 0.25, 0.5))}
                  title="Zoom Out (-)"
                  aria-label="Zoom Out"
                >
                  <ZoomOut size={13} />
                </button>
                <span className="zoom-percentage">{Math.round(zoomLevel * 100)}%</span>
                <button
                  type="button"
                  className="btn-zoom"
                  onClick={() => setZoomLevel((prev) => Math.min(prev + 0.25, 4))}
                  title="Zoom In (+)"
                  aria-label="Zoom In"
                >
                  <ZoomIn size={13} />
                </button>
                <button
                  type="button"
                  className="btn-zoom"
                  onClick={() => {
                    setZoomLevel(1);
                    setPanOffset({ x: 0, y: 0 });
                  }}
                  title="Reset Zoom (0)"
                  aria-label="Reset Zoom"
                >
                  <Maximize2 size={13} />
                </button>
              </div>
            </div>

            {/* Canvas Stage */}
            <div
              ref={containerRef}
              className={`preview-canvas-stage ${zoomLevel > 1 ? 'is-draggable' : ''}`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
            >
              {viewMode === 'split' && hasUpscaledImage ? (
                <div className="preview-split-viewport">
                  {/* Background Original Crop */}
                  <img
                    src={cropImageUrl}
                    alt="Original Crop"
                    className="preview-split-img preview-original-img"
                    style={{
                      transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                    }}
                    draggable={false}
                  />

                  {/* Foreground HD Image clipped */}
                  <div
                    className="preview-split-overlay"
                    style={{ clipPath: `inset(0 ${100 - splitPos}% 0 0)` }}
                  >
                    <img
                      src={hdImageUrl}
                      alt="HD Enhanced"
                      className="preview-split-img preview-hd-img"
                      style={{
                        transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                      }}
                      draggable={false}
                    />
                  </div>

                  {/* Split Slider Handle */}
                  <div
                    className="preview-split-handle"
                    style={{ left: `${splitPos}%` }}
                  >
                    <div className="preview-handle-line" />
                    <div className="preview-handle-circle">
                      <Split size={12} />
                    </div>
                  </div>

                  {/* Range Slider for Interaction */}
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={splitPos}
                    onChange={(e) => setSplitPos(Number(e.target.value))}
                    className="preview-slider-input"
                    aria-label="Compare HD Enhanced versus Original Crop"
                  />

                  <div className="preview-split-labels">
                    <span className="split-label left">HD Enhanced</span>
                    <span className="split-label right">Original Crop</span>
                  </div>
                </div>
              ) : viewMode === 'source' && hasSourceImage ? (
                <div className="preview-source-wrapper">
                  <img
                    src={sourceImageUrl}
                    alt="Source lookbook sheet"
                    className="preview-source-img"
                    style={{
                      transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                    }}
                    draggable={false}
                  />
                  {currentItem.bbox && currentItem.bbox.length === 4 && (
                    <div
                      className="preview-source-bbox-highlight"
                      style={{
                        top: `${currentItem.bbox[0] * 100}%`,
                        left: `${currentItem.bbox[1] * 100}%`,
                        height: `${(currentItem.bbox[2] - currentItem.bbox[0]) * 100}%`,
                        width: `${(currentItem.bbox[3] - currentItem.bbox[1]) * 100}%`,
                        transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                      }}
                    >
                      <span className="bbox-tag">{currentItem.label}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="preview-single-wrapper">
                  <img
                    src={viewMode === 'crop' ? cropImageUrl : hdImageUrl}
                    alt={currentItem.label}
                    className="preview-garment-main-img"
                    style={{
                      transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                      cursor: zoomLevel > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default',
                    }}
                    draggable={false}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar: Garment Quality & Feature Inspector */}
          <div className="wardrobe-preview-inspector">
            {/* Title & Category Info */}
            <div className="inspector-card-section">
              <h2 id="garment-modal-title" className="inspector-garment-title">
                {currentItem.label}
              </h2>
              <div className="inspector-meta-row">
                <span className="inspector-id-code">ID: {currentItem.id}</span>
                {currentItem.created_at && (
                  <span className="inspector-date-code">
                    {new Date(currentItem.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                )}
              </div>
            </div>

            {/* AI Quality & High-Fidelity Specs */}
            <div className="inspector-specs-container">
              <div className="inspector-specs-header">
                <ShieldCheck size={14} className="text-accent" />
                <span>AI Material & Quality Specs</span>
              </div>

              {/* Fabric & Material */}
              <div className="inspector-spec-item">
                <span className="spec-label">Fabric / Texture</span>
                <span className="spec-value">
                  {details.fabric_texture || 'Standard garment weave'}
                </span>
              </div>

              {/* Garment Silhouette */}
              {details.garment_type && (
                <div className="inspector-spec-item">
                  <span className="spec-label">Silhouette / Type</span>
                  <span className="spec-value">{details.garment_type}</span>
                </div>
              )}

              {/* Color Palette */}
              <div className="inspector-spec-item">
                <span className="spec-label">Palette</span>
                <div className="spec-palette-row">
                  {details.primary_color ? (
                    <div className="palette-chip" title={`Primary: ${details.primary_color}`}>
                      <Palette size={12} className="text-muted" />
                      <span>{details.primary_color}</span>
                    </div>
                  ) : (
                    <span className="spec-value-muted">Auto-detected</span>
                  )}
                  {Array.isArray(details.secondary_colors) && details.secondary_colors.length > 0 && (
                    <div className="secondary-colors-wrap">
                      {details.secondary_colors.map((c, i) => (
                        <span key={i} className="palette-secondary-tag">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Hardware / Trims */}
              {details.hardware_and_details && (
                <div className="inspector-spec-item">
                  <span className="spec-label">Hardware & Details</span>
                  <span className="spec-value">{details.hardware_and_details}</span>
                </div>
              )}

              {/* Text / Typography Lock */}
              {details.has_text_or_logo && details.exact_text_content?.length > 0 && (
                <div className="inspector-spec-item highlight-cyan">
                  <div className="spec-header-with-action">
                    <span className="spec-label text-cyan-400">
                      <FileText size={12} /> Exact Text Lock
                    </span>
                    <button
                      type="button"
                      className="btn-copy-tiny"
                      onClick={() => handleCopyText(details.exact_text_content.join(' '))}
                      title="Copy text to clipboard"
                    >
                      {copiedText ? <Check size={10} className="text-green-400" /> : 'Copy'}
                    </button>
                  </div>
                  <div className="exact-text-chips">
                    {details.exact_text_content.map((txt, i) => (
                      <span key={i} className="exact-text-tag">
                        {txt}
                      </span>
                    ))}
                  </div>
                  {details.logo_and_print_placement && (
                    <span className="placement-hint">
                      Placement: {details.logo_and_print_placement}
                    </span>
                  )}
                </div>
              )}

              {/* Graphic Print & Motif */}
              {details.has_graphic_or_print && details.graphic_description && (
                <div className="inspector-spec-item highlight-purple">
                  <span className="spec-label text-purple-400">
                    <Tag size={12} /> Graphic Artwork Lock
                  </span>
                  <span className="spec-value text-purple-200">
                    {details.graphic_description}
                  </span>
                  {details.logo_and_print_placement && (
                    <span className="placement-hint">
                      Placement: {details.logo_and_print_placement}
                    </span>
                  )}
                </div>
              )}

              {/* Upscale Resolution & Quality Status */}
              <div className="inspector-spec-item">
                <span className="spec-label">Upscale Status</span>
                <div className="status-indicator-row">
                  {isUpscaled ? (
                    <span className="status-badge-success">
                      <Sparkles size={12} />
                      <span>4K Ultra-HD Enhanced</span>
                    </span>
                  ) : currentItem.upscale_status === 'pending' || currentItem.upscale_status === 'processing' ? (
                    <span className="status-badge-pending">
                      <Sparkles size={12} className="animate-spin" />
                      <span>Enhancing Details...</span>
                    </span>
                  ) : (
                    <span className="status-badge-neutral">
                      <span>Standard Crop Resolution</span>
                    </span>
                  )}
                </div>
              </div>

              {/* API Cost & Token Metrics */}
              {Number(currentItem.cost_usd || 0) > 0 && (
                <div className="inspector-spec-item highlight-emerald">
                  <span className="spec-label text-emerald-400">
                    <DollarSign size={12} /> API Generation Cost
                  </span>
                  <span className="spec-value text-emerald-300 font-mono">
                    ${Number(currentItem.cost_usd).toFixed(4)} ({currentItem.tokens || 0} tokens)
                  </span>
                </div>
              )}
            </div>

            {/* Actions Footer */}
            <div className="inspector-actions-footer">
              <button
                type="button"
                className="btn-primary-glow"
                onClick={() => {
                  onAddAssignment?.(currentItem, { x: 0.5, y: 0.5 });
                  onClose?.();
                }}
                title="Add garment to composition queue"
              >
                <Layers size={15} />
                <span>Pin & Swap onto Subject</span>
              </button>

              <button
                type="button"
                className="btn-danger-outline"
                onClick={(e) => {
                  if (onDeleteItem) {
                    onDeleteItem(e, currentItem.id);
                    onClose?.();
                  }
                }}
                title="Remove this garment from library"
              >
                <Trash2 size={14} />
                <span>Delete Garment</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
