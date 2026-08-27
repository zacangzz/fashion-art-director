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
  history = [],
  onExportMasterPrepared,
}) {
  const originalRatio =
    generationResult?.aspect_ratio ||
    activeBaseline?.aspect_ratio ||
    globalAspectRatio ||
    '1.8:1';

  // Check if current generation result is already a prepared master
  const isAlreadyMaster = Boolean(
    generationResult?.schema_json?.is_export_master ||
    generationResult?.schema_dict?.is_export_master ||
    (generationResult?.id || generationResult?.generation_id || '').startsWith('gen_export_')
  );

  // If already master, look up parent in history to retrieve original generated image
  const parentFromHistory = isAlreadyMaster && generationResult?.parent_id
    ? history.find((h) => h.id === generationResult.parent_id)
    : null;

  const originalImage =
    (isAlreadyMaster && parentFromHistory
      ? parentFromHistory.master_image_url || parentFromHistory.image_url
      : null) ||
    (!isAlreadyMaster ? generationResult?.master_image_url : null) ||
    activeBaseline?.image_url ||
    generationResult?.master_image_url ||
    null;

  const originalGenId =
    (isAlreadyMaster && parentFromHistory
      ? parentFromHistory.id
      : null) ||
    (!isAlreadyMaster ? generationResult?.generation_id || generationResult?.id : null) ||
    activeBaseline?.id ||
    generationResult?.generation_id ||
    'original';

  const [preparedMaster, setPreparedMaster] = useState(
    isAlreadyMaster ? generationResult : null
  );
  const [isPreparing, setIsPreparing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isDownloadingOriginal, setIsDownloadingOriginal] = useState(false);
  const [isDownloadingUpscaled, setIsDownloadingUpscaled] = useState(false);
  const [compareMode, setCompareMode] = useState('split'); // 'split' | 'enhanced' | 'original'
  const [sliderPos, setSliderPos] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const seed = generationResult?.seed ?? activeBaseline?.seed ?? '—';
  const prompt =
    generationResult?.compiled_prompt ||
    activeBaseline?.compiled_prompt ||
    '—';

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

  // Resolutions metadata
  const originalWidth =
    parentFromHistory?.resolution_width ||
    (!isAlreadyMaster && (generationResult?.resolution?.width || generationResult?.resolution_width)) ||
    1080;
  const originalHeight =
    parentFromHistory?.resolution_height ||
    (!isAlreadyMaster && (generationResult?.resolution?.height || generationResult?.resolution_height)) ||
    1620;
  const originalResolutionText = `${originalWidth} × ${originalHeight} px`;

  const upscaledWidth =
    preparedMaster?.resolution?.width ||
    preparedMaster?.resolution_width ||
    3840;
  const upscaledHeight =
    preparedMaster?.resolution?.height ||
    preparedMaster?.resolution_height ||
    3840;
  const upscaledResolutionText = `${upscaledWidth} × ${upscaledHeight} px`;

  const handlePrepareExport = async () => {
    if (!originalGenId) return;
    setIsPreparing(true);
    setErrorMessage(null);

    try {
      const result = await prepareExport(originalGenId);
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

  const handleDownloadOriginal = async () => {
    if (!originalImage) return;
    setIsDownloadingOriginal(true);
    try {
      const response = await fetch(originalImage);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fileGenId = originalGenId || 'original';
      a.download = `original_export_${fileGenId}_${originalRatio.replace(/[:.]/g, '_')}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download original image:', err);
      setErrorMessage('Failed to download original image file.');
    } finally {
      setIsDownloadingOriginal(false);
    }
  };

  const handleDownloadUpscaled = async () => {
    const upscaledUrl = preparedMaster?.master_image_url;
    if (!upscaledUrl) return;
    setIsDownloadingUpscaled(true);
    try {
      const response = await fetch(upscaledUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fileGenId = preparedMaster?.generation_id || originalGenId || 'upscaled';
      a.download = `upscaled_master_${fileGenId}_${originalRatio.replace(/[:.]/g, '_')}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download upscaled master image:', err);
      setErrorMessage('Failed to download upscaled master image file.');
    } finally {
      setIsDownloadingUpscaled(false);
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
          <span className="badge-meta">Generation: #{originalGenId || 'none'}</span>
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
                  {isReady
                    ? `${upscaledResolutionText} (4K Raw Master)`
                    : `${originalResolutionText} (Standard Base)`}
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
          {/* Card 1: Prepare for Export */}
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
                  <span className="thumbnail-title">Generation #{originalGenId || '—'}</span>
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

          {/* Card 2: Download Options (Original vs Upscaled) */}
          <div className="export-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <ShieldCheck size={16} className="text-accent" />
                <span className="card-title">2. Download Options</span>
              </div>
              <span className="badge-pill">Master Files</span>
            </div>

            <div className="export-options-body">
              <p className="bundle-description">
                Download the original un-upscaled generation or the high-resolution AI-upscaled master directly to your device.
              </p>

              <div className="export-download-options-list">
                {/* Option A: Original Generated Image */}
                <div className="export-download-item-card">
                  <div className="export-download-item-header">
                    <div className="download-item-title-group">
                      <FileImage size={16} className="text-muted" />
                      <span className="download-item-title">Original Generated Image</span>
                    </div>
                    <span className="badge-meta">Base Render</span>
                  </div>

                  <div className="download-item-specs-grid">
                    <div className="download-spec-item">
                      <span className="download-spec-label">Format</span>
                      <span className="download-spec-val">PNG</span>
                    </div>
                    <div className="download-spec-item">
                      <span className="download-spec-label">Aspect Ratio</span>
                      <span className="download-spec-val">{originalRatio}</span>
                    </div>
                    <div className="download-spec-item">
                      <span className="download-spec-label">Resolution</span>
                      <span className="download-spec-val">{originalResolutionText}</span>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="btn-secondary export-action-btn download-original-btn"
                    onClick={handleDownloadOriginal}
                    disabled={!originalImage || isDownloadingOriginal}
                  >
                    <Download size={15} />
                    <span>
                      {isDownloadingOriginal
                        ? 'Downloading Original...'
                        : 'Download Original Image (.png)'}
                    </span>
                  </button>
                </div>

                {/* Option B: AI-Upscaled 4K Master */}
                <div className={`export-download-item-card ${isReady ? 'ready' : ''}`}>
                  <div className="export-download-item-header">
                    <div className="download-item-title-group">
                      <Sparkles size={16} className={isReady ? 'text-accent' : 'text-muted'} />
                      <span className="download-item-title">AI-Upscaled Master</span>
                    </div>
                    {isReady ? (
                      <span className="export-status-pill ready">
                        <CheckCircle2 size={11} /> 4K Ready
                      </span>
                    ) : (
                      <span className="export-status-pill pending">
                        Pending Step 1
                      </span>
                    )}
                  </div>

                  <div className="download-item-specs-grid">
                    <div className="download-spec-item">
                      <span className="download-spec-label">Format</span>
                      <span className="download-spec-val">Lossless PNG</span>
                    </div>
                    <div className="download-spec-item">
                      <span className="download-spec-label">Aspect Ratio</span>
                      <span className="download-spec-val">{originalRatio}</span>
                    </div>
                    <div className="download-spec-item">
                      <span className="download-spec-label">Resolution</span>
                      <span className="download-spec-val">
                        {isReady ? `${upscaledResolutionText} (4K)` : '4K (Upscale)'}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="btn-accent export-action-btn download-upscaled-btn"
                    onClick={handleDownloadUpscaled}
                    disabled={!isReady || isDownloadingUpscaled}
                  >
                    {isReady ? <Download size={15} /> : <Sparkles size={15} />}
                    <span>
                      {isDownloadingUpscaled
                        ? 'Downloading Master...'
                        : isReady
                        ? 'Download Upscaled Master (.png)'
                        : 'Prepare in Step 1 to Download'}
                    </span>
                  </button>

                  {!isReady && (
                    <span className="download-hint-text">
                      Click <strong>Prepare for Export</strong> in Step 1 above to generate the 4K AI-upscaled master.
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

