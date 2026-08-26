import React, { useState } from 'react';
import {
  Download,
  Package,
  FileImage,
  Check,
  Layers,
  Info,
  Grid,
  Maximize2,
  CheckCircle2,
} from 'lucide-react';

export const RATIO_PRESETS = [
  {
    id: '1:1',
    label: '1:1 Square',
    res: '1440 × 1440 px',
    width: 1440,
    height: 1440,
    aspectRatio: '1 / 1',
    desc: 'Standard high-res square formats & feed carousels',
    badge: 'Universal',
  },
  {
    id: '4:5',
    label: '4:5 Social Feed',
    res: '1080 × 1350 px',
    width: 1080,
    height: 1350,
    aspectRatio: '4 / 5',
    desc: 'Instagram portrait, Pinterest & mobile feed posts',
    badge: 'Social Focus',
  },
  {
    id: '9:16',
    label: '9:16 Story / Reels',
    res: '1080 × 1920 px',
    width: 1080,
    height: 1920,
    aspectRatio: '9 / 16',
    desc: 'Instagram Stories, TikTok & full vertical screens',
    badge: 'Vertical Story',
  },
  {
    id: '1.85:1',
    label: '1.85:1 Wide Banner',
    res: '1440 × 780 px',
    width: 1440,
    height: 780,
    aspectRatio: '1440 / 780',
    desc: 'Hero banners, headers & widescreen displays',
    badge: 'Hero Banner',
  },
  {
    id: '1.8:1',
    label: '1.8:1 Display Card',
    res: '1730 × 960 px',
    width: 1730,
    height: 960,
    aspectRatio: '1730 / 960',
    desc: 'Desktop displays, presentation cards & cards',
    badge: 'Display Landscape',
  },
  {
    id: '4k:16:9',
    label: '16:9 4K UHD Master',
    res: '3840 × 2160 px',
    width: 3840,
    height: 2160,
    aspectRatio: '16 / 9',
    desc: 'Ultra-HD 4K displays, horizontal prints & billboard assets',
    badge: '4K Print / UHD',
  },
  {
    id: '4k:9:16',
    label: '9:16 4K Vertical Poster',
    res: '2160 × 3840 px',
    width: 2160,
    height: 3840,
    aspectRatio: '9 / 16',
    desc: 'Large vertical gallery posters & 4K kiosk displays',
    badge: '4K Poster',
  },
  {
    id: '4k:1:1',
    label: '1:1 4K Square Print',
    res: '2160 × 2160 px',
    width: 2160,
    height: 2160,
    aspectRatio: '1 / 1',
    desc: 'High-res square fine art & exhibition catalog prints',
    badge: '4K Fine Art',
  },
];


export default function ExportStudio({
  generationResult,
  activeBaseline,
  onExportBundle,
  isExporting = false,
}) {
  const [exportFormat, setExportFormat] = useState('png');
  const [jpegQuality, setJpegQuality] = useState(95);
  const [selectedRatioId, setSelectedRatioId] = useState('1:1');
  const [isDownloadingSingle, setIsDownloadingSingle] = useState(false);
  const [downloadingRatioId, setDownloadingRatioId] = useState(null);

  const activeImage = generationResult?.master_image_url || activeBaseline?.image_url || null;
  const activeGenId = generationResult?.generation_id || activeBaseline?.id || null;
  const seed = generationResult?.seed || activeBaseline?.seed || '—';
  const prompt = generationResult?.compiled_prompt || activeBaseline?.compiled_prompt || '—';

  const selectedPreset = RATIO_PRESETS.find((r) => r.id === selectedRatioId) || RATIO_PRESETS[0];

  // Helper to crop and download a specific aspect ratio client-side
  const handleDownloadSpecificRatio = async (preset) => {
    if (!activeImage) return;
    setDownloadingRatioId(preset.id);
    try {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = activeImage;
      });

      const srcW = img.naturalWidth || img.width;
      const srcH = img.naturalHeight || img.height;
      const targetW = preset.width;
      const targetH = preset.height;
      const targetRatio = targetW / targetH;
      const srcRatio = srcW / srcH;

      let cropW, cropH, cropX, cropY;
      if (srcRatio > targetRatio) {
        cropH = srcH;
        cropW = Math.round(srcH * targetRatio);
        cropX = Math.round((srcW - cropW) / 2);
        cropY = 0;
      } else {
        cropW = srcW;
        cropH = Math.round(srcW / targetRatio);
        cropX = 0;
        cropY = Math.round((srcH - cropH) / 2);
      }

      const canvas = document.createElement('canvas');
      canvas.width = targetW;
      canvas.height = targetH;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, cropX, cropY, cropW, cropH, 0, 0, targetW, targetH);

      const mime = exportFormat === 'jpeg' ? 'image/jpeg' : 'image/png';
      const quality = exportFormat === 'jpeg' ? jpegQuality / 100 : undefined;

      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeRatioName = preset.id.replace(/[:.]/g, '_');
        a.download = `artwork_${activeGenId || 'master'}_${safeRatioName}.${exportFormat}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setDownloadingRatioId(null);
      }, mime, quality);
    } catch (err) {
      console.error('Failed to export specific ratio crop:', err);
      setDownloadingRatioId(null);
    }
  };

  const handleDownloadMaster = async () => {
    if (!activeImage) return;
    setIsDownloadingSingle(true);
    try {
      const response = await fetch(activeImage);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `master_${activeGenId || 'image'}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download master image:', err);
    } finally {
      setIsDownloadingSingle(false);
    }
  };

  return (
    <div className="export-studio-container" role="region" aria-label="Export Production Studio">
      {/* Top Header */}
      <div className="export-studio-header">
        <div className="export-header-info">
          <div className="export-title-row">
            <Package size={20} className="text-accent" />
            <h2>Export & Multi-Ratio Production Studio</h2>
          </div>
          <p className="export-subtitle">
            Preview, inspect, and package your creative assets across all 5 standard production ratios or export the full ZIP bundle.
          </p>
        </div>

        <div className="export-header-summary-badge">
          <span className="badge-meta">Generation: #{activeGenId || 'master'}</span>
          <span className="badge-seed">Seed: #{seed}</span>
        </div>
      </div>

      {/* Aspect Ratio Live Previews Grid */}
      <div className="export-ratio-previews-section">
        <div className="export-section-header">
          <div className="section-title-group">
            <Grid size={16} className="text-accent" />
            <h3>Aspect Ratio Crops Live Preview</h3>
          </div>
          <span className="section-subtitle">
            Live center-cropped representations across all 5 production standards. Click any card to inspect or export directly.
          </span>
        </div>

        <div className="export-ratio-cards-grid" role="tablist" aria-label="Aspect Ratio Previews">
          {RATIO_PRESETS.map((preset) => {
            const isSelected = selectedRatioId === preset.id;
            const isDownloading = downloadingRatioId === preset.id;

            return (
              <div
                key={preset.id}
                className={`ratio-preview-card ${isSelected ? 'is-selected' : ''}`}
                onClick={() => setSelectedRatioId(preset.id)}
                role="tab"
                aria-selected={isSelected}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setSelectedRatioId(preset.id);
                  }
                }}
              >
                {/* Ratio Header */}
                <div className="ratio-card-header">
                  <div className="ratio-badge-group">
                    <span className="ratio-tag-pill">{preset.id}</span>
                    <span className="ratio-category-badge">{preset.badge}</span>
                  </div>
                  {isSelected && (
                    <span className="ratio-selected-indicator" title="Selected for enlarged inspection">
                      <Check size={12} /> Selected
                    </span>
                  )}
                </div>

                {/* Aspect Ratio Preview Frame */}
                <div className="ratio-crop-frame-wrapper">
                  <div
                    className="ratio-crop-viewport"
                    style={{ aspectRatio: preset.aspectRatio }}
                  >
                    {activeImage ? (
                      <img
                        src={activeImage}
                        alt={`Preview in ${preset.label} format`}
                        className="ratio-crop-img"
                        loading="lazy"
                      />
                    ) : (
                      <div className="ratio-crop-empty">
                        <FileImage size={24} className="text-muted" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Info & Action Footer */}
                <div className="ratio-card-footer">
                  <div className="ratio-info-col">
                    <span className="ratio-label-text">{preset.label}</span>
                    <span className="ratio-res-text">{preset.res}</span>
                  </div>
                  <button
                    type="button"
                    className="ratio-download-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownloadSpecificRatio(preset);
                    }}
                    disabled={!activeImage || isDownloading}
                    title={`Export cropped ${preset.id} ${exportFormat.toUpperCase()}`}
                    aria-label={`Export ${preset.label} image`}
                  >
                    <Download size={13} />
                    <span>{isDownloading ? '...' : exportFormat.toUpperCase()}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Two-Column Control Panel */}
      <div className="export-studio-grid">
        {/* Left Column: Enlarged Selected Ratio Inspector */}
        <div className="export-preview-column">
          <div className="export-card preview-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <Maximize2 size={16} className="text-accent" />
                <span className="card-title">
                  Inspector: {selectedPreset.label} ({selectedPreset.id})
                </span>
              </div>
              <span className="badge-meta">{selectedPreset.res}</span>
            </div>

            <div className="export-inspector-viewport">
              <div
                className="inspector-crop-container"
                style={{ aspectRatio: selectedPreset.aspectRatio }}
              >
                {activeImage ? (
                  <img
                    src={activeImage}
                    alt={`Enlarged preview for ${selectedPreset.label}`}
                    className="inspector-preview-img"
                  />
                ) : (
                  <div className="export-empty-placeholder">
                    <FileImage size={48} className="text-muted" />
                    <p>No active generation selected for export.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Metadata Footer */}
            <div className="export-metadata-hud">
              <div className="metadata-row">
                <span className="meta-label">Optimal Placement:</span>
                <span className="meta-value">{selectedPreset.desc}</span>
              </div>
              <div className="metadata-row">
                <span className="meta-label">Prompt:</span>
                <span className="meta-value prompt-clamp">{prompt}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Master & Bundle Download Actions */}
        <div className="export-actions-column">
          {/* Format Settings & Single Master Export */}
          <div className="export-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <Download size={16} />
                <span className="card-title">Master File Export</span>
              </div>
            </div>

            <div className="export-options-body">
              <div className="export-field-row">
                <label className="field-label" htmlFor="export-format-group">File Format:</label>
                <div id="export-format-group" className="format-toggle-group" role="group" aria-label="Export format">
                  <button
                    type="button"
                    className={`format-btn ${exportFormat === 'png' ? 'active' : ''}`}
                    onClick={() => setExportFormat('png')}
                    aria-pressed={exportFormat === 'png'}
                  >
                    PNG (Lossless)
                  </button>
                  <button
                    type="button"
                    className={`format-btn ${exportFormat === 'jpeg' ? 'active' : ''}`}
                    onClick={() => setExportFormat('jpeg')}
                    aria-pressed={exportFormat === 'jpeg'}
                  >
                    JPEG (Compressed)
                  </button>
                </div>
              </div>

              {exportFormat === 'jpeg' && (
                <div className="export-field-row">
                  <div className="field-label-between">
                    <label className="field-label" htmlFor="jpeg-quality-slider">JPEG Quality:</label>
                    <span className="quality-value">{jpegQuality}%</span>
                  </div>
                  <input
                    id="jpeg-quality-slider"
                    type="range"
                    min="75"
                    max="100"
                    value={jpegQuality}
                    onChange={(e) => setJpegQuality(Number(e.target.value))}
                    className="slider-input"
                    aria-label="JPEG Compression Quality"
                  />
                </div>
              )}

              <div className="export-btn-stack">
                <button
                  type="button"
                  className="btn-primary export-action-btn"
                  onClick={handleDownloadMaster}
                  disabled={!activeImage || isDownloadingSingle}
                >
                  <Download size={16} />
                  <span>
                    {isDownloadingSingle ? 'Preparing Master...' : `Download Full Master (${exportFormat.toUpperCase()})`}
                  </span>
                </button>

                <button
                  type="button"
                  className="btn-secondary export-action-btn"
                  onClick={() => handleDownloadSpecificRatio(selectedPreset)}
                  disabled={!activeImage || downloadingRatioId === selectedPreset.id}
                >
                  <Download size={15} />
                  <span>
                    {downloadingRatioId === selectedPreset.id
                      ? `Exporting ${selectedPreset.id}...`
                      : `Download ${selectedPreset.label} Crop (${selectedPreset.id})`}
                  </span>
                </button>
              </div>
            </div>
          </div>

          {/* Multi-Ratio & 4K Production Bundle */}
          <div className="export-card">
            <div className="export-card-header">
              <div className="card-title-group">
                <Package size={16} />
                <span className="card-title">1-Click Production & 4K Print Bundle</span>
              </div>
              <span className="badge-pill">300 DPI ZIP</span>
            </div>

            <div className="export-options-body">
              <p className="bundle-description">
                Batch renders all centered social & 4K print crops with embedded 300 DPI metadata and generation audit lineage:
              </p>

              <ul className="bundle-presets-bullet-list">
                {RATIO_PRESETS.map((p) => (
                  <li key={p.id} className="bundle-preset-bullet">
                    <span className="bullet-pill">{p.id}</span>
                    <span className="bullet-title">{p.label}</span>
                    <span className="bullet-res">{p.res}</span>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="btn-accent export-action-btn bundle-btn"
                onClick={() => onExportBundle?.(activeGenId)}
                disabled={!activeGenId || isExporting}
              >
                <Package size={16} />
                <span>
                  {isExporting ? 'Packaging Production ZIP...' : 'Download Production & 4K Bundle (.ZIP)'}
                </span>
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
