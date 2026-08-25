import React, { useState } from 'react';
import {
  CheckCircle2,
  ArrowRight,
  Eye,
  Hash,
  Clock,
  Sparkles,
  Terminal,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export default function BaselineSelector({
  baselines = [],
  selectedBaselineId,
  onSelectBaseline,
  onProceedToStudio,
}) {
  const [zoomedImage, setZoomedImage] = useState(null);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [isPromptExpanded, setIsPromptExpanded] = useState(false);

  if (!baselines || baselines.length === 0) {
    return null;
  }

  const activeBaseline = baselines.find((b) => b.id === selectedBaselineId) || baselines[0];
  const activeBaselinePrompt = activeBaseline?.compiled_prompt || activeBaseline?.prompt || '';

  const handleCopyPrompt = async () => {
    if (!activeBaselinePrompt) return;
    try {
      await navigator.clipboard.writeText(activeBaselinePrompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    } catch (err) {
      console.error('Failed to copy prompt to clipboard', err);
    }
  };

  return (
    <div className="baseline-selector-container">
      <div className="baseline-header">
        <div>
          <div className="baseline-badge">
            <Sparkles size={14} />
            <span>Step 1 Complete</span>
          </div>
          <h2 className="baseline-title">Select Foundation Baseline Candidate</h2>
          <p className="baseline-subtitle">
            Choose 1 of the 4 rendered candidate seeds to lock as your visual foundation for fine-tuning.
          </p>
        </div>

        <button
          type="button"
          className="btn-primary baseline-proceed-btn"
          onClick={() => onProceedToStudio && onProceedToStudio(activeBaseline)}
          disabled={!activeBaseline}
        >
          <span>Select & Launch Visual Graph Studio</span>
          <ArrowRight size={16} />
        </button>
      </div>

      {/* 4-Quadrant Grid */}
      <div className="baseline-grid">
        {baselines.map((baseline, index) => {
          const isSelected = baseline.id === (selectedBaselineId || activeBaseline?.id);

          return (
            <div
              key={baseline.id}
              className={`baseline-card ${isSelected ? 'baseline-card-selected' : ''}`}
              onClick={() => onSelectBaseline && onSelectBaseline(baseline)}
            >
              <div className="baseline-image-wrapper">
                <img
                  src={baseline.image_url}
                  alt={`Baseline candidate #${index + 1}`}
                  className="baseline-image"
                  loading="lazy"
                />

                <div className="baseline-overlay">
                  <button
                    type="button"
                    className="baseline-preview-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setZoomedImage(baseline.image_url);
                    }}
                    title="Zoom Preview"
                  >
                    <Eye size={16} />
                  </button>
                </div>

                {isSelected && (
                  <div className="baseline-selected-badge">
                    <CheckCircle2 size={16} />
                    <span>Selected Baseline</span>
                  </div>
                )}
              </div>

              <div className="baseline-info-footer">
                <div className="baseline-seed-tag">
                  <Hash size={12} />
                  <span>Seed #{baseline.seed}</span>
                </div>
                <div className="baseline-time-tag">
                  <Clock size={12} />
                  <span>Candidate {index + 1}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {/* Baseline Full Prompt Submitted to API Inspector */}
      {activeBaselinePrompt && (
        <div className="baseline-prompt-panel">
          <div className="baseline-prompt-header">
            <div className="baseline-prompt-title-group">
              <Terminal size={14} className="text-accent" />
              <span className="baseline-prompt-title">Full Prompt Submitted to API (Candidate Foundation)</span>
              <span className="baseline-prompt-tag">Seed #{activeBaseline.seed}</span>
            </div>

            <div className="baseline-prompt-actions">
              <button
                type="button"
                className="btn-prompt-action"
                onClick={handleCopyPrompt}
                title="Copy Full Baseline Prompt"
              >
                {copiedPrompt ? (
                  <>
                    <Check size={12} className="text-success" />
                    <span className="text-success">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Copy Prompt</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-prompt-action"
                onClick={() => setIsPromptExpanded(!isPromptExpanded)}
                title={isPromptExpanded ? "Collapse" : "Expand"}
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
            className={`baseline-prompt-content ${isPromptExpanded ? 'expanded' : 'collapsed'}`}
          >
            {activeBaselinePrompt}
          </div>
        </div>
      )}

      {/* Zoom Modal */}
      {zoomedImage && (
        <div className="modal-backdrop" onClick={() => setZoomedImage(null)}>
          <div className="modal-content-zoom" onClick={(e) => e.stopPropagation()}>
            <img src={zoomedImage} alt="Zoomed baseline preview" className="zoomed-image" />
            <button
              type="button"
              className="modal-close-btn"
              onClick={() => setZoomedImage(null)}
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
