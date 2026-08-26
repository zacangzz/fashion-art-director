import React, { useState, useRef } from 'react';
import {
  Download,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileImage,
  Maximize2,
  Sliders,
  Eye,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { prepareExport } from '../services/apiClient';

export default function ExportStudio({
  generationResult,
  activeBaseline,
  globalAspectRatio = '1.8:1',
  onExportMasterPrepared,
}) {
  const originalRatio =
    generationResult?.aspect_ratio ||
    activeBaseline?.aspect_ratio ||
    globalAspectRatio ||
    '1.8:1';

  const originalImage =
    generationResult?.master_image_url ||
    activeBaseline?.image_url ||
    null;

  const activeGenId =
    generationResult?.generation_id ||
    activeBaseline?.id ||
    null;

  const seed = generationResult?.seed ?? activeBaseline?.seed ?? '—';
  const prompt =
    generationResult?.compiled_prompt ||
    activeBaseline?.compiled_prompt ||
    '—';

  // Check if current generation result is already a prepared master
  const isAlreadyMaster = Boolean(
    generationResult?.schema_json?.is_export_master ||
    generationResult?.schema_dict?.is_export_master
  );

  const [preparedMaster, setPreparedMaster] = useState(
    isAlreadyMaster ? generationResult : null
  );
  const [isPreparing, setIsPreparing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [compareMode, setCompareMode] = useState('split'); // 'split' | 'enhanced' | 'original'
  const [sliderPos, setSliderPos] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const finalImageUrl = preparedMaster?.master_image_url || originalImage;
  const isReady = Boolean(preparedMaster?.master_image_url);

  // Compute CSS aspect ratio style string (e.g., "2 / 3", "1.8 / 1")
  const cssAspectRatio = (() => {
    if (!originalRatio) return '1 / 1';
    const parts = originalRatio.split(':');
    if (parts.length === 2) {
      return `${parts[0]} / ${parts[1]}`;
    }
    return '1 / 1';
  })();

  const handlePrepareExport = async () => {
    if (!activeGenId) return;
    setIsPreparing(true);
    setErrorMessage(null);

    try {
      const result = await prepareExport(activeGenId);
      setPreparedMaster(result);
      setCompareMode('split');
      onExportMasterPrepared?.(result);
    } catch (err) {
      console.error('Failed to prepare export master:', err);
      setErrorMessage(err.message || 'Failed to prepare image for export.');
    } finally {
      setIsPreparing(false);
    }
  };

  const handleDownloadMaster = async () => {
    if (!finalImageUrl) return;
    setIsDownloading(true);
    try {
      const response = await fetch(finalImageUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fileGenId = preparedMaster?.generation_id || activeGenId || 'master';
      a.download = `master_export_${fileGenId}_${originalRatio.replace(/[:.]/g, '_')}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download master image:', err);
      setErrorMessage('Failed to download master image file.');
    } finally {
      setIsDownloading(false);
    }
  };

  // Slider drag handlers for split-comparison
  const handleMouseDown = () => setIsDragging(true);
  const handleMouseUp = () => setIsDragging(false);
  const handleMouseMove = (e) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setSliderPos(Math.round((x / rect.width) * 100));
  };
  const handleTouchMove = (e) => {
    if (!containerRef.current || !e.touches[0]) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.touches[0].clientX - rect.left, rect.width));
    setSliderPos(Math.round((x / rect.width) * 100));
  };

  return (
    <div
      className="export-studio-container"
      role="region"
      aria-label="Export Production Studio"
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Top Header */}
      <div className="export-studio-header">
        <div className="export-header-info">
          <div className="export-title-row">
            <Sparkles size={22} className="text-accent" />
            <h2>Master Export & AI Restoration Studio</h2>
          </div>
          <p className="export-subtitle">
            Enhance, restore, and prepare your artwork in its original aspect ratio with Gemini AI before exporting raw master files.
          </p>
        </div>

        <div className="export-header-summary-badge">
          <span className="badge-meta">Format: {originalRatio}</span>
          <span className="badge-meta">Generation: #{activeGenId || 'none'}</span>
          <span className="badge-seed">Seed: #{seed}</span>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="export-error-banner" role="alert">
          <AlertCircle size={18} className="text-error" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="export-studio-grid">
        {/* Left Column: Inspector & Interactive Viewport */}
        <div className="export-preview-column">
          <div className="export-card preview-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <Maximize2 size={16} className="text-accent" />
                <span className="card-title">
                  Master Inspector ({originalRatio})
                </span>
                {isReady && (
                  <span className="export-status-pill ready">
                    <CheckCircle2 size={12} /> AI Enhanced Master Ready
                  </span>
                )}
                {!isReady && (
                  <span className="export-status-pill pending">
                    Original Preview
                  </span>
                )}
              </div>

              {/* View Mode Controls (when prepared) */}
              {isReady && originalImage && (
                <div className="export-view-modes" role="group" aria-label="Comparison mode">
                  <button
                    type="button"
                    className={`view-mode-btn ${compareMode === 'split' ? 'active' : ''}`}
                    onClick={() => setCompareMode('split')}
                    title="Interactive Split Comparison"
                  >
                    <Sliders size={13} /> Split
                  </button>
                  <button
                    type="button"
                    className={`view-mode-btn ${compareMode === 'enhanced' ? 'active' : ''}`}
                    onClick={() => setCompareMode('enhanced')}
                    title="View Enhanced Master"
                  >
                    <Sparkles size={13} /> Enhanced
                  </button>
                  <button
                    type="button"
                    className={`view-mode-btn ${compareMode === 'original' ? 'active' : ''}`}
                    onClick={() => setCompareMode('original')}
                    title="View Original Preview"
                  >
                    <Eye size={13} /> Original
                  </button>
                </div>
              )}
            </div>

            {/* Viewport Canvas */}
            <div className="export-inspector-viewport">
              {originalImage ? (
                <div
                  className="export-split-viewport"
                  style={{ aspectRatio: cssAspectRatio }}
                >
                  {/* Base Image Layer: Visible in Original mode, or as Left half in Split mode */}
                  <img
                    src={compareMode === 'enhanced' ? finalImageUrl : originalImage}
                    alt={compareMode === 'enhanced' ? 'Enhanced Master' : 'Original Artwork'}
                    className="export-viewport-img base-layer"
                  />

                  {/* Split Comparison Mode Overlay */}
                  {isReady && compareMode === 'split' && (
                    <>
                      {/* Clipped Enhanced Image Overlay */}
                      <div
                        className="export-split-clipped-layer"
                        style={{
                          clipPath: `inset(0 0 0 ${sliderPos}%)`,
                        }}
                      >
                        <img
                          src={preparedMaster.master_image_url}
                          alt="AI Enhanced Master"
                          className="export-viewport-img"
                        />
                      </div>

                      <span className="split-label original-tag">Original</span>
                      <span className="split-label enhanced-tag">AI Enhanced 4K Master</span>

                      {/* Split Divider Line */}
                      <div
                        className="split-divider-line"
                        style={{ left: `${sliderPos}%` }}
                      >
                        <div className="split-handle">
                          <Sliders size={13} />
                        </div>
                      </div>

                      {/* Interactive Drag/Touch Range Input */}
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={sliderPos}
                        onChange={(e) => setSliderPos(Number(e.target.value))}
                        className="split-range-input"
                        aria-label="Before/After Split Comparison Slider"
                      />
                    </>
                  )}
                </div>
              ) : (
                <div className="export-empty-placeholder">
                  <FileImage size={48} className="text-muted" />
                  <p>No active generation selected for export.</p>
                </div>
              )}
            </div>

            {/* Inspector HUD Info */}
            <div className="export-metadata-hud">
              <div className="metadata-row">
                <span className="meta-label">Aspect Ratio:</span>
                <span className="meta-value">{originalRatio} (Original Selected Format)</span>
              </div>
              <div className="metadata-row">
                <span className="meta-label">Master Resolution:</span>
                <span className="meta-value">
                  {preparedMaster?.resolution
                    ? `${preparedMaster.resolution.width} × ${preparedMaster.resolution.height} px (4K Raw Master)`
                    : `${generationResult?.resolution_width || 3840} × ${generationResult?.resolution_height || 3840} px (4K Base)`}
                </span>
              </div>
              <div className="metadata-row">
                <span className="meta-label">Prompt Task:</span>
                <span className="meta-value">4K Master Restoration (Garment & Texture Enhancement)</span>
              </div>
              <div className="metadata-row">
                <span className="meta-label">Original Prompt:</span>
                <span className="meta-value prompt-clamp">{prompt}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Workflow Control & Download Action */}
        <div className="export-actions-column">
          {/* Card: Prepare for Export */}
          <div className="export-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <Zap size={16} className="text-accent" />
                <span className="card-title">1. AI Master Preparation</span>
              </div>
              <span className="badge-pill">Gemini AI</span>
            </div>

            <div className="export-options-body">
              {/* Preview Thumbnail Widget */}
              <div className="export-thumbnail-card">
                <div className="thumbnail-frame" style={{ aspectRatio: cssAspectRatio }}>
                  {originalImage ? (
                    <img src={originalImage} alt="Chosen Preview" className="thumbnail-img" />
                  ) : (
                    <FileImage size={24} className="text-muted" />
                  )}
                </div>
                <div className="thumbnail-details">
                  <span className="thumbnail-title">Chosen Generation #{activeGenId || '—'}</span>
                  <span className="thumbnail-meta">Format: {originalRatio}</span>
                  <span className="thumbnail-meta">Seed: #{seed}</span>
                </div>
              </div>

              <div className="export-workflow-description">
                <p>
                  Click <strong>Prepare for Export</strong> to run Gemini image restoration and upscaling on this artwork.
                  The AI refines garment fabrics, restores facial clarity, and maximizes output fidelity in the original aspect ratio.
                </p>
              </div>

              <button
                type="button"
                className={`btn-primary export-action-btn prepare-btn ${isPreparing ? 'is-loading' : ''}`}
                onClick={handlePrepareExport}
                disabled={!originalImage || isPreparing}
              >
                <Sparkles size={16} className={isPreparing ? 'animate-spin' : ''} />
                <span>
                  {isPreparing
                    ? 'Enhancing with Gemini AI...'
                    : isReady
                    ? 'Re-Prepare for Export'
                    : 'Prepare for Export'}
                </span>
              </button>
            </div>
          </div>

          {/* Card: Master File Download */}
          <div className="export-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <ShieldCheck size={16} className="text-accent" />
                <span className="card-title">2. Download Master File</span>
              </div>
              <span className="badge-pill">Raw Lossless PNG</span>
            </div>

            <div className="export-options-body">
              <p className="bundle-description">
                Download the raw uncompressed master artwork in full fidelity ({originalRatio}) directly to your device.
              </p>

              <div className="export-format-badge-box">
                <div className="format-info-item">
                  <span className="format-info-label">Format</span>
                  <span className="format-info-val">Lossless PNG</span>
                </div>
                <div className="format-info-item">
                  <span className="format-info-label">Aspect Ratio</span>
                  <span className="format-info-val">{originalRatio}</span>
                </div>
                <div className="format-info-item">
                  <span className="format-info-label">Fidelity</span>
                  <span className="format-info-val">{isReady ? 'AI Enhanced Master' : 'Original Raw'}</span>
                </div>
              </div>

              <button
                type="button"
                className="btn-accent export-action-btn download-master-btn"
                onClick={handleDownloadMaster}
                disabled={!finalImageUrl || isDownloading}
              >
                <Download size={16} />
                <span>
                  {isDownloading
                    ? 'Downloading Master...'
                    : isReady
                    ? 'Download High Quality Master (.png)'
                    : 'Download Original Master (.png)'}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
