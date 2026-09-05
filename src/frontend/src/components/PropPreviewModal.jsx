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
  Coins,
  Box,
} from 'lucide-react';
import { upscaleProp } from '../services/apiClient';
import { formatSpendSGD, formatTokens } from '../utils/formatters';
import { PROP_CATEGORY_COLORS } from '../constants/propCategories';

export default function PropPreviewModal({
  isOpen = false,
  onClose,
  items = [],
  initialItemId = null,
  onAddAssignment,
  onDeleteItem,
  onUpdateItem,
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [viewMode, setViewMode] = useState('hd'); // 'hd', 'crop', 'split', 'source'
  const [splitPos, setSplitPos] = useState(50);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [copiedText, setCopiedText] = useState(false);
  const [isUpscalingCurrent, setIsUpscalingCurrent] = useState(false);
  const [upscaleError, setUpscaleError] = useState(null);

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

  const handleManualUpscale = async () => {
    if (!currentItem || isUpscalingCurrent) return;
    try {
      setIsUpscalingCurrent(true);
      setUpscaleError(null);
      const res = await upscaleProp(currentItem.id);
      if (res && onUpdateItem) {
        onUpdateItem(res);
      }
    } catch (err) {
      setUpscaleError(err.message || 'Failed to upscale prop.');
    } finally {
      setIsUpscalingCurrent(false);
    }
  };

  if (!isOpen || !currentItem) return null;

  const catColor = PROP_CATEGORY_COLORS[currentItem.category] || PROP_CATEGORY_COLORS.decor;
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
      aria-labelledby="prop-modal-title"
    >
      <div
        className="wardrobe-preview-modal-container"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="wardrobe-preview-header">
          <div className="wardrobe-preview-title-group">
            <div className="wardrobe-preview-badge">
              <Box size={16} className="text-accent" />
              <span>Prop Quality Inspector</span>
            </div>
            <span
              id="prop-modal-title"
              className="wardrobe-preview-item-title"
            >
              {currentItem.label || 'Prop Item'}
            </span>
            <span
              className="garment-cat-tag"
              style={{
                color: catColor,
                borderColor: `${catColor}40`,
                backgroundColor: `${catColor}15`,
              }}
            >
              {currentItem.category || 'decor'}
            </span>
            {isUpscaled && (
              <span className="hd-upscaled-pill">
                <Sparkles size={11} />
                <span>4K HD Master</span>
              </span>
            )}
          </div>

          <div className="wardrobe-preview-header-actions">
            {/* View Mode Switcher */}
            <div className="wardrobe-view-modes-group" role="group" aria-label="Image view options">
              <button
                type="button"
                className={`view-mode-pill ${viewMode === 'hd' ? 'active' : ''}`}
                onClick={() => setViewMode('hd')}
                disabled={!hasUpscaledImage}
                title={hasUpscaledImage ? 'View 4K AI-Enhanced Asset' : '4K Enhancement not yet generated'}
              >
                <Sparkles size={12} />
                <span>4K Enhanced</span>
              </button>
              <button
                type="button"
                className={`view-mode-pill ${viewMode === 'crop' ? 'active' : ''}`}
                onClick={() => setViewMode('crop')}
                title="View Segmented Crop"
              >
                <ImageIcon size={12} />
                <span>Original Crop</span>
              </button>
              {hasUpscaledImage && (
                <button
                  type="button"
                  className={`view-mode-pill ${viewMode === 'split' ? 'active' : ''}`}
                  onClick={() => setViewMode('split')}
                  title="Interactive Split Comparison"
                >
                  <Split size={12} />
                  <span>Split A/B</span>
                </button>
              )}
              {hasSourceImage && (
                <button
                  type="button"
                  className={`view-mode-pill ${viewMode === 'source' ? 'active' : ''}`}
                  onClick={() => setViewMode('source')}
                  title="View Full Catalog Sheet"
                >
                  <Eye size={12} />
                  <span>Full Sheet</span>
                </button>
              )}
            </div>

            <button
              type="button"
              className="btn-icon-subtle"
              onClick={onClose}
              aria-label="Close Inspector"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Main Body */}
        <div className="wardrobe-preview-body">
          {/* Left: Viewport */}
          <div
            ref={containerRef}
            className="wardrobe-preview-viewport"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onWheel={handleWheel}
            style={{ cursor: zoomLevel > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
          >
            {/* Split Comparison Mode */}
            {viewMode === 'split' && hasUpscaledImage ? (
              <div className="wardrobe-split-wrapper">
                <img
                  src={cropImageUrl}
                  alt="Original segmented prop"
                  className="split-underlay-img"
                />
                <div
                  className="split-overlay-crop"
                  style={{ width: `${splitPos}%` }}
                >
                  <img
                    src={hdImageUrl}
                    alt="4K Enhanced prop"
                    className="split-overlay-img"
                  />
                  <div className="split-overlay-tag">4K HD</div>
                </div>
                <div className="split-underlay-tag">Original Crop</div>
                <div
                  className="split-divider-bar"
                  style={{ left: `${splitPos}%` }}
                >
                  <div className="split-handle-nub">
                    <Split size={14} />
                  </div>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={splitPos}
                  onChange={(e) => setSplitPos(Number(e.target.value))}
                  className="split-range-input"
                  aria-label="Split comparison position slider"
                />
              </div>
            ) : (
              <div
                className="wardrobe-zoom-container"
                style={{
                  transform: `scale(${zoomLevel}) translate(${panOffset.x / zoomLevel}px, ${panOffset.y / zoomLevel}px)`,
                  transition: isPanning ? 'none' : 'transform 0.15s ease-out',
                }}
              >
                <img
                  src={
                    viewMode === 'source'
                      ? sourceImageUrl
                      : viewMode === 'hd' && hasUpscaledImage
                      ? hdImageUrl
                      : cropImageUrl
                  }
                  alt={currentItem.label || 'Prop preview'}
                  className="wardrobe-preview-img"
                  draggable={false}
                />
              </div>
            )}

            {/* Viewport Floating Zoom Controls */}
            <div className="wardrobe-zoom-controls">
              <button
                type="button"
                className="zoom-btn"
                onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 4))}
                title="Zoom In (+)"
                aria-label="Zoom In"
              >
                <ZoomIn size={14} />
              </button>
              <span className="zoom-level-text">{Math.round(zoomLevel * 100)}%</span>
              <button
                type="button"
                className="zoom-btn"
                onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 0.5))}
                title="Zoom Out (-)"
                aria-label="Zoom Out"
              >
                <ZoomOut size={14} />
              </button>
              <button
                type="button"
                className="zoom-btn"
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

            {/* Pagination Floating Arrows */}
            {items.length > 1 && (
              <>
                <button
                  type="button"
                  className="wardrobe-nav-btn prev-btn"
                  onClick={handlePrev}
                  aria-label="Previous prop"
                  title="Previous prop (Left Arrow)"
                >
                  <ChevronLeft size={22} />
                </button>
                <button
                  type="button"
                  className="wardrobe-nav-btn next-btn"
                  onClick={handleNext}
                  aria-label="Next prop"
                  title="Next prop (Right Arrow)"
                >
                  <ChevronRight size={22} />
                </button>
              </>
            )}
          </div>

          {/* Right: Technical Inspector Sidebar */}
          <div className="wardrobe-preview-sidebar">
            {/* Quick Action: Add to Scene */}
            <div className="sidebar-action-card">
              <button
                type="button"
                className="btn-primary w-full"
                style={{ padding: '0.65rem 1rem', fontSize: '0.85rem' }}
                onClick={() => {
                  onAddAssignment?.(currentItem, { x: 0.5, y: 0.5 });
                  onClose?.();
                }}
              >
                <Layers size={14} />
                <span>Place Prop in Scene</span>
              </button>
            </div>

            {/* 4K Upscale Section */}
            <div className="sidebar-meta-card">
              <div className="meta-card-header">
                <div className="meta-title-row">
                  <Sparkles size={14} className="text-accent" />
                  <span className="meta-heading">Asset Definition</span>
                </div>
                <span className={`status-pill ${currentItem.upscale_status || 'completed'}`}>
                  {currentItem.upscale_status === 'processing'
                    ? 'Upscaling...'
                    : currentItem.upscale_status === 'pending'
                    ? 'Queued'
                    : isUpscaled
                    ? '4K Ultra-Res'
                    : 'Standard Crop'}
                </span>
              </div>

              <div className="meta-spec-grid">
                <div className="spec-row">
                  <span className="spec-label">Resolution</span>
                  <span className="spec-val">
                    {currentItem.resolution || (isUpscaled ? '3840 × 2160' : 'Cropped Definition')}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Enhancement</span>
                  <span className="spec-val">
                    {isUpscaled ? 'Gemini 3.1 4K AI Upscaler' : 'Auto-Crop'}
                  </span>
                </div>
              </div>

              {!isUpscaled && currentItem.upscale_status !== 'processing' && (
                <button
                  type="button"
                  className="btn-secondary w-full"
                  style={{ marginTop: '0.75rem', fontSize: '0.78rem' }}
                  onClick={handleManualUpscale}
                  disabled={isUpscalingCurrent}
                >
                  <Sparkles size={13} />
                  <span>{isUpscalingCurrent ? 'Enhancing with AI...' : 'Generate 4K HD Master'}</span>
                </button>
              )}

              {upscaleError && (
                <div className="sidebar-error-text">{upscaleError}</div>
              )}
            </div>

            {/* Extracted Details & Feature Extraction */}
            <div className="sidebar-meta-card">
              <div className="meta-card-header">
                <div className="meta-title-row">
                  <Sliders size={14} className="text-accent" />
                  <span className="meta-heading">Material & Scene Context</span>
                </div>
              </div>

              <div className="meta-spec-grid">
                <div className="spec-row">
                  <span className="spec-label">Material / Finish</span>
                  <span className="spec-val">
                    {details.material_finish || details.fabric_or_material || 'Natural / Studio finish'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Placement Hint</span>
                  <span className="spec-val">
                    {details.placement_hint || 'Tabletop or floor standing'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Scale Preset</span>
                  <span className="spec-val" style={{ textTransform: 'capitalize' }}>
                    {currentItem.scale_preset || 'Medium (0.30)'}
                  </span>
                </div>
              </div>

              {/* Color Palette Swatches */}
              {details.color_palette && details.color_palette.length > 0 && (
                <div className="meta-subsection">
                  <span className="subsection-label">
                    <Palette size={12} />
                    <span>Identified Colors</span>
                  </span>
                  <div className="palette-swatches-row">
                    {details.color_palette.map((colorHex, idx) => (
                      <div
                        key={idx}
                        className="palette-swatch-item"
                        title={colorHex}
                        onClick={() => handleCopyText(colorHex)}
                      >
                        <div
                          className="color-swatch-circle"
                          style={{ backgroundColor: colorHex }}
                        />
                        <span className="color-swatch-name">{colorHex}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Features & Details */}
              {details.details && (
                <div className="meta-subsection">
                  <span className="subsection-label">
                    <FileText size={12} />
                    <span>Description & Features</span>
                  </span>
                  <p className="garment-details-para">{details.details}</p>
                </div>
              )}
            </div>

            {/* Audit & Spend Transparency Card */}
            <div className="sidebar-meta-card">
              <div className="meta-card-header">
                <div className="meta-title-row">
                  <Coins size={14} className="text-accent" />
                  <span className="meta-heading">Compute & Cost Telemetry</span>
                </div>
                <span className="obs-badge obs-badge-props" style={{ fontSize: '0.62rem' }}>
                  props
                </span>
              </div>

              <div className="meta-spec-grid">
                <div className="spec-row">
                  <span className="spec-label">Compute Spend</span>
                  <span className="spec-val highlight-amber">
                    {formatSpendSGD(currentItem.cost_sgd, currentItem.cost_usd)}
                  </span>
                </div>
                {currentItem.token_usage && (
                  <div className="spec-row">
                    <span className="spec-label">Token Footprint</span>
                    <span className="spec-val">
                      {formatTokens(currentItem.token_usage.total_tokens || currentItem.token_usage.output_tokens)}
                    </span>
                  </div>
                )}
                {currentItem.created_at && (
                  <div className="spec-row">
                    <span className="spec-label">Ingested</span>
                    <span className="spec-val" style={{ fontSize: '0.72rem' }}>
                      {new Date(currentItem.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Footer / Delete */}
            <div className="sidebar-footer-row">
              <span className="item-counter-sub">
                Item {currentIndex + 1} of {items.length}
              </span>
              <button
                type="button"
                className="btn-text-danger"
                onClick={(e) => onDeleteItem?.(e, currentItem.id)}
                title="Delete this prop"
                aria-label={`Delete ${currentItem.label}`}
              >
                <Trash2 size={13} />
                <span>Remove</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
