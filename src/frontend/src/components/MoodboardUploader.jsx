import React, { useRef, useState } from 'react';
import { Upload, X, FileText, Sparkles, Loader2, MessageSquareText } from 'lucide-react';

export default function MoodboardUploader({
  files = [],
  onFilesChange,
  prompt = '',
  onPromptChange,
  onAnalyze,
  isAnalyzing = false,
}) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState(null);

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
              * Please provide a starting prompt. The vision model will fuse your uploaded references with this prompt to generate 4 baseline candidates.
            </span>
          ) : (
            <span>
              The AI Vision Director will synthesize your moodboard references together with this prompt to craft the optimal Master Prompt, 9-category visual levers, and 4 baseline candidates.
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
            <span>Analyzing & Generating 4 Baselines...</span>
          </>
        ) : (
          <>
            <Sparkles size={16} />
            <span>
              {files.length === 0
                ? 'Upload 1–5 Reference Files to Begin'
                : !prompt.trim()
                ? 'Enter Starting Prompt to Generate Baselines'
                : 'Analyze & Generate 4 Baselines'}
            </span>
          </>
        )}
      </button>
    </div>
  );
}

