import React, { useRef, useState } from 'react';
import {
  Upload,
  X,
  FileText,
  Sparkles,
  Loader2,
  MessageSquareText,
  Ratio,
  RectangleHorizontal,
  Square,
  RectangleVertical,
  Image as ImageIcon,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

import {
  ASPECT_RATIO_OPTIONS,
  detectClosestRatio,
} from '../constants/aspectRatios';

export { detectClosestRatio };

export default function MoodboardUploader({
  files = [],
  onFilesChange,
  prompt = '',
  onPromptChange,
  onAnalyze,
  isAnalyzing = false,
  aspectRatio = '1:1',
  onAspectRatioChange = null,
  onDirectPhotoUpload = null,
  isDirectUploading = false,
}) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // Direct Photo Ingestion (Skip Art Direction) state
  const directFileInputRef = useRef(null);
  const [isDirectDragOver, setIsDirectDragOver] = useState(false);
  const [directFile, setDirectFile] = useState(null);
  const [directPreviewUrl, setDirectPreviewUrl] = useState(null);
  const [directDimensions, setDirectDimensions] = useState(null);
  const [detectedRatio, setDetectedRatio] = useState('1:1');
  const [chosenRatio, setChosenRatio] = useState('1:1');
  const [directUploadError, setDirectUploadError] = useState(null);

  const handleDirectFileSelected = (file) => {
    setDirectUploadError(null);
    if (!file) return;

    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setDirectUploadError('Only PNG, JPEG, and WebP images are supported.');
      return;
    }

    const preview = URL.createObjectURL(file);
    setDirectFile(file);
    setDirectPreviewUrl(preview);

    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      setDirectDimensions({ width: w, height: h });
      const matchedRatio = detectClosestRatio(w, h);
      setDetectedRatio(matchedRatio);
      setChosenRatio(matchedRatio);
    };
    img.onerror = () => {
      setDirectDimensions(null);
      setDetectedRatio('1:1');
      setChosenRatio('1:1');
    };
    img.src = preview;
  };

  const handleClearDirectFile = (e) => {
    if (e && typeof e.stopPropagation === 'function') {
      e.stopPropagation();
    }
    if (directPreviewUrl) {
      URL.revokeObjectURL(directPreviewUrl);
    }
    setDirectFile(null);
    setDirectPreviewUrl(null);
    setDirectDimensions(null);
    setDirectUploadError(null);
    if (directFileInputRef.current) {
      directFileInputRef.current.value = '';
    }
  };

  const handleProceedDirectUpload = async () => {
    if (!directFile || !onDirectPhotoUpload) return;
    try {
      await onDirectPhotoUpload(directFile, chosenRatio);
    } catch (err) {
      setDirectUploadError(err.message || 'Failed to upload photo.');
    }
  };

  const handleFilesAdded = (incomingFiles) => {
    setUploadError(null);
    const validFiles = Array.from(incomingFiles).filter((f) =>
      ['image/png', 'image/jpeg', 'image/webp', 'application/pdf'].includes(f.type)
    );

    if (validFiles.length !== incomingFiles.length) {
      setUploadError('Only PNG, JPEG, WebP, and PDF files are allowed.');
    }

    const combined = [...files, ...validFiles].slice(0, 5);
    if (combined.length > 5) {
      setUploadError('Maximum of 5 files can be analyzed at once.');
    }

    onFilesChange(combined);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleRemoveFile = (index) => {
    const updated = files.filter((_, i) => i !== index);
    onFilesChange(updated);
  };

  const handleAnalyzeClick = () => {
    if (onAnalyze) {
      onAnalyze(prompt);
    }
  };

  return (
    <div className="step-1-uploader-column">
      {/* Primary Card: Moodboard Ingestion */}
      <div className="moodboard-uploader-card">
        <div className="card-header">
          <div className="card-title-group">
            <Upload size={16} className="text-accent" />
            <span className="card-title">Moodboard Ingestion</span>
          </div>
          <span className="badge-counter">{files.length}/5 files</span>
        </div>

        {/* Drag & Drop Zone */}
        <div
          className={`dropzone ${isDragOver ? 'dropzone-active' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp,application/pdf"
            style={{ display: 'none' }}
            onChange={(e) => {
              if (e.target.files) handleFilesAdded(e.target.files);
            }}
          />

          <div className="dropzone-icon">
            <Upload size={28} />
          </div>
          <p className="dropzone-text">
            Drop 1–5 reference images or PDFs here, or <span>browse</span>
          </p>
          <p className="dropzone-hint">Supports PNG, JPG, WebP & PDF specifications</p>
        </div>

        {uploadError && <div className="error-chip">{uploadError}</div>}

        {/* File Previews */}
        {files.length > 0 && (
          <div className="file-preview-grid">
            {files.map((file, idx) => {
              const isPdf = file.type === 'application/pdf';
              const previewUrl = isPdf ? null : URL.createObjectURL(file);

              return (
                <div key={`${file.name}-${idx}`} className="file-preview-item">
                  {isPdf ? (
                    <div className="pdf-preview-box">
                      <FileText size={20} />
                      <span className="file-name">{file.name}</span>
                    </div>
                  ) : (
                    <img src={previewUrl} alt={file.name} className="image-preview-thumb" />
                  )}

                  <button
                    type="button"
                    className="file-remove-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveFile(idx);
                    }}
                    title="Remove file"
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Creative Baseline & Tone Prompt (Required) */}
        <div className="baseline-prompt-section">
          <div className="baseline-prompt-header">
            <div className="baseline-prompt-title-group">
              <MessageSquareText size={14} className="text-accent" />
              <label htmlFor="baseline-prompt-input" className="baseline-prompt-label">
                Starting Scene Prompt <span style={{ color: '#ef4444' }}>*</span>
              </label>
            </div>
            <span
              className="baseline-prompt-badge"
              style={{
                background: !prompt.trim() ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                color: !prompt.trim() ? '#f87171' : '#10b981',
                border: `1px solid ${!prompt.trim() ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
              }}
            >
              {!prompt.trim() ? 'Required' : 'Ready'}
            </span>
          </div>
          <textarea
            id="baseline-prompt-input"
            className="baseline-prompt-textarea"
            rows={3}
            value={prompt}
            onChange={(e) => onPromptChange && onPromptChange(e.target.value)}
            placeholder="Enter the required starting scene direction, characters, mood, setting, lighting, and style overrides (e.g. 'A high-fashion editorial portrait in a sunlit modernist villa with tailored neutral wardrobe and warm film tones')..."
            disabled={isAnalyzing}
            required
          />
          <div className="baseline-prompt-hint">
            {!prompt.trim() ? (
              <span style={{ color: '#fb923c' }}>
                * Please provide a starting prompt. The vision model will analyze your uploaded references with this prompt to extract visual levers and synthesize the Master Prompt.
              </span>
            ) : (
              <span>
                The AI Vision Director will analyze your moodboard references together with this prompt to synthesize the Master Generation Prompt and 9-category visual levers for your review.
              </span>
            )}
          </div>
        </div>

        {/* Primary Action Button */}
        <button
          type="button"
          className="btn-primary"
          onClick={handleAnalyzeClick}
          disabled={files.length === 0 || !prompt.trim() || isAnalyzing}
          style={{ width: '100%', marginTop: '4px' }}
        >
          {isAnalyzing ? (
            <>
              <Loader2 size={16} className="spin-animation" />
              <span>Analyzing Moodboard & Synthesizing Levers...</span>
            </>
          ) : (
            <>
              <Sparkles size={16} />
              <span>
                {files.length === 0
                  ? 'Upload 1–5 Reference Files to Begin'
                  : !prompt.trim()
                  ? 'Enter Starting Prompt to Analyze'
                  : 'Analyze Moodboard'}
              </span>
            </>
          )}
        </button>
      </div>

      {/* Secondary Card: Skip Art Direction — Direct Photo Ingestion */}
      <div className="direct-upload-card">
        <div className="card-header">
          <div className="card-title-group">
            <ImageIcon size={16} className="text-emerald-400" />
            <span className="card-title">Direct Photo Ingestion</span>
          </div>
          <span className="badge-counter badge-skip-art">Skip Art Direction</span>
        </div>

        <p className="direct-upload-description">
          Already have a starting image or high-res photo? Upload it here to skip moodboard direction and jump straight into <strong>Step 2 (Refinement Studio)</strong>.
        </p>

        {!directFile ? (
          <div
            className={`dropzone direct-dropzone ${isDirectDragOver ? 'dropzone-active' : ''}`}
            onDrop={(e) => {
              e.preventDefault();
              setIsDirectDragOver(false);
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleDirectFileSelected(e.dataTransfer.files[0]);
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDirectDragOver(true);
            }}
            onDragLeave={() => setIsDirectDragOver(false)}
            onClick={() => directFileInputRef.current?.click()}
            role="button"
            tabIndex={0}
          >
            <input
              ref={directFileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleDirectFileSelected(e.target.files[0]);
                }
              }}
            />
            <div className="dropzone-icon" style={{ color: '#10b981' }}>
              <Upload size={24} />
            </div>
            <p className="dropzone-text">
              Drop 1 photo here, or <span>browse</span>
            </p>
            <p className="dropzone-hint">PNG, JPG or WebP (Full Master Resolution)</p>
          </div>
        ) : (
          <div className="direct-preview-container">
            <div className="direct-preview-card">
              <div className="direct-preview-image-box">
                <img src={directPreviewUrl} alt="Uploaded direct photo" className="direct-preview-thumb" />
                <button
                  type="button"
                  className="file-remove-btn"
                  onClick={handleClearDirectFile}
                  title="Remove uploaded image"
                  disabled={isDirectUploading}
                >
                  <X size={12} />
                </button>
              </div>

              <div className="direct-preview-meta">
                <div className="direct-meta-name" title={directFile.name}>
                  {directFile.name}
                </div>
                <div className="direct-meta-specs">
                  {directDimensions
                    ? `${directDimensions.width} × ${directDimensions.height} px`
                    : `${(directFile.size / (1024 * 1024)).toFixed(2)} MB`}
                  {' • '}
                  <span className="text-emerald-400" style={{ fontWeight: 600 }}>
                    Detected: {detectedRatio}
                  </span>
                </div>

                <div className="direct-ratio-selector-row">
                  <span className="direct-ratio-label">Aspect Ratio:</span>
                  <select
                    className="direct-ratio-select"
                    value={chosenRatio}
                    onChange={(e) => setChosenRatio(e.target.value)}
                    disabled={isDirectUploading}
                  >
                    {ASPECT_RATIO_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.name} {opt.id === detectedRatio ? '(Auto-Detected)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <button
              type="button"
              className="btn-primary direct-submit-btn"
              onClick={handleProceedDirectUpload}
              disabled={isDirectUploading}
            >
              {isDirectUploading ? (
                <>
                  <Loader2 size={16} className="spin-animation" />
                  <span>Registering Photo & Initializing Studio...</span>
                </>
              ) : (
                <>
                  <span>Skip Art Direction & Begin Refinement</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        )}

        {directUploadError && <div className="error-chip" style={{ marginTop: '8px' }}>{directUploadError}</div>}
      </div>
    </div>
  );
}


