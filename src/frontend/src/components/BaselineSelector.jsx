import React, { useState, useEffect } from 'react';
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
  Layers,
  Palette,
  FileText,
  LayoutGrid,
  Columns4,
  Maximize2,
  Scan,
  Ratio,
} from 'lucide-react';
import { CATEGORIES } from '../utils/defaultTags';

/**
 * Parses aspect ratio strings (e.g., '9:16', '16:9', '1:1', '2:3', '1.8:1')
 * and returns CSS aspect-ratio value, numeric ratio, orientation, and formatted label.
 */
export function parseAspectRatio(aspectRatioStr) {
  if (!aspectRatioStr) {
    return {
      cssRatio: '2 / 3',
      ratioValue: 2 / 3,
      orientation: 'vertical',
      label: '2:3',
    };
  }

  let ratioValue = 2 / 3;
  let cssRatio = '2 / 3';
  const label = aspectRatioStr;

  if (aspectRatioStr.includes(':')) {
    const [wStr, hStr] = aspectRatioStr.split(':');
    const w = parseFloat(wStr);
    const h = parseFloat(hStr);
    if (!isNaN(w) && !isNaN(h) && h > 0) {
      ratioValue = w / h;
      cssRatio = `${w} / ${h}`;
    }
  } else {
    const val = parseFloat(aspectRatioStr);
    if (!isNaN(val) && val > 0) {
      ratioValue = val;
      cssRatio = `${val} / 1`;
    }
  }

  let orientation = 'vertical';
  if (ratioValue >= 0.95 && ratioValue <= 1.05) {
    orientation = 'square';
  } else if (ratioValue > 1.05) {
    orientation = 'horizontal';
  } else {
    orientation = 'vertical';
  }

  return {
    cssRatio,
    ratioValue,
    orientation,
    label,
  };
}

export const ASPECT_RATIO_PREVIEWS = {
  '1:1': { width: 1080, height: 1080 },
  '16:9': { width: 1920, height: 1080 },
  '9:16': { width: 1080, height: 1920 },
  '21:9': { width: 2560, height: 1080 },
  '2:3': { width: 1080, height: 1620 },
  '3:2': { width: 1620, height: 1080 },
  '4:5': { width: 1080, height: 1350 },
  '5:4': { width: 1350, height: 1080 },
  '3:4': { width: 1080, height: 1440 },
  '4:3': { width: 1440, height: 1080 },
  '1.8:1': { width: 1920, height: 1067 },
  '1.85:1': { width: 1998, height: 1080 },
};

export const ASPECT_RATIO_MASTERS = {
  '1:1': { width: 3840, height: 3840 },
  '16:9': { width: 3840, height: 2160 },
  '9:16': { width: 2160, height: 3840 },
  '21:9': { width: 3840, height: 1645 },
  '2:3': { width: 2560, height: 3840 },
  '3:2': { width: 3840, height: 2560 },
  '4:5': { width: 3072, height: 3840 },
  '5:4': { width: 3840, height: 3072 },
  '3:4': { width: 2880, height: 3840 },
  '4:3': { width: 3840, height: 2880 },
  '1.8:1': { width: 3840, height: 2133 },
  '1.85:1': { width: 3840, height: 2075 },
};

export function getBaseResolution(aspectRatioStr) {
  return ASPECT_RATIO_PREVIEWS[aspectRatioStr] || { width: 1080, height: 1080 };
}

export function getMasterResolution(aspectRatioStr) {
  return ASPECT_RATIO_MASTERS[aspectRatioStr] || { width: 3840, height: 3840 };
}


export default function BaselineSelector({
  baselines = [],
  selectedBaselineId,
  onSelectBaseline,
  onProceedToStudio,
  tagState = null,
  aspectRatio = null,
}) {
  const [zoomedImage, setZoomedImage] = useState(null);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [isPromptExpanded, setIsPromptExpanded] = useState(false);
  const [copiedMoodboard, setCopiedMoodboard] = useState(false);
  const [isMoodboardExpanded, setIsMoodboardExpanded] = useState(true);

  // View settings: fitMode ('contain' | 'cover'), layoutMode ('auto' | '4' | '2')
  const [fitMode, setFitMode] = useState('contain');
  const [layoutMode, setLayoutMode] = useState('auto');

  // Close zoomed modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && zoomedImage) {
        setZoomedImage(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [zoomedImage]);

  if (!baselines || baselines.length === 0) {
    return null;
  }

  const activeBaseline = baselines.find((b) => b.id === selectedBaselineId) || baselines[0];
  const activeBaselinePrompt = activeBaseline?.compiled_prompt || activeBaseline?.prompt || '';

  // Determine current active aspect ratio
  const activeRatioStr =
    activeBaseline?.aspect_ratio ||
    baselines.find((b) => b.aspect_ratio)?.aspect_ratio ||
    aspectRatio ||
    '2:3';
  const currentRatioInfo = parseAspectRatio(activeRatioStr);

  // Compute effective columns: if auto, 9:16/vertical uses 4 columns so all 4 fit on screen side-by-side
  const effectiveColumns =
    layoutMode === 'auto'
      ? currentRatioInfo.orientation === 'vertical' && baselines.length === 4
        ? 4
        : 2
      : parseInt(layoutMode, 10) || 2;

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

  const handleCopyMoodboardInfo = async () => {
    if (!tagState) return;
    try {
      let text = '';
      if (tagState.master_prompt) {
        text += `[Master Prompt]\n${tagState.master_prompt}\n\n`;
      }
      if (tagState.categories) {
        text += `[Extracted Visual Levers (9 Categories)]\n`;
        for (const cat of CATEGORIES) {
          const list = tagState.categories[cat.key] || [];
          if (list.length > 0) {
            const tagStrs = list.map((t) => {
              if (typeof t === 'string') return t;
              return `${t.label}${t.weight && t.weight !== 1.0 ? ` (${t.weight.toFixed(1)}x)` : ''}`;
            });
            text += `• ${cat.label}: ${tagStrs.join(', ')}\n`;
          }
        }
      }
      await navigator.clipboard.writeText(text.trim());
      setCopiedMoodboard(true);
      setTimeout(() => setCopiedMoodboard(false), 2000);
    } catch (err) {
      console.error('Failed to copy moodboard info to clipboard', err);
    }
  };

  // Calculate stats for moodboard info
  const hasMoodboardInfo = Boolean(
    tagState &&
      (tagState.master_prompt ||
        (tagState.categories && Object.keys(tagState.categories).length > 0))
  );

  const categoriesWithTags = CATEGORIES.filter((cat) => {
    const list = tagState?.categories?.[cat.key];
    return Array.isArray(list) && list.length > 0;
  });

  const totalTagsCount = categoriesWithTags.reduce((acc, cat) => {
    return acc + (tagState.categories[cat.key]?.length || 0);
  }, 0);

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
            Choose 1 of the {baselines.length} rendered candidate seeds to lock as your visual foundation for fine-tuning.
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

      {/* Grid Controls: View Layout, Fit/Fill Toggle & Dynamic Aspect Ratio Badge */}
      <div className="baseline-controls-bar">
        <div className="baseline-controls-left">
          <div className="baseline-aspect-indicator" title={`Current aspect ratio: ${currentRatioInfo.label}`}>
            <Ratio size={14} className="text-accent" />
            <span className="baseline-aspect-text">
              Canvas: <strong>{currentRatioInfo.label}</strong> ({currentRatioInfo.orientation})
            </span>
          </div>
        </div>

        <div className="baseline-controls-right">
          {/* Fit vs Fill Frame Mode Toggle */}
          <div className="baseline-toggle-group" role="group" aria-label="Image Fit Mode">
            <button
              type="button"
              className={`baseline-toggle-btn ${fitMode === 'contain' ? 'active' : ''}`}
              onClick={() => setFitMode('contain')}
              title="Fit to Canvas (Full uncropped image)"
            >
              <Scan size={13} />
              <span>Fit (Full)</span>
            </button>
            <button
              type="button"
              className={`baseline-toggle-btn ${fitMode === 'cover' ? 'active' : ''}`}
              onClick={() => setFitMode('cover')}
              title="Fill Frame (Cover)"
            >
              <Maximize2 size={13} />
              <span>Fill</span>
            </button>
          </div>

          {/* 4-Columns vs 2x2 Layout Switcher */}
          {baselines.length > 2 && (
            <div className="baseline-toggle-group" role="group" aria-label="Grid Layout">
              <button
                type="button"
                className={`baseline-toggle-btn ${effectiveColumns === 4 ? 'active' : ''}`}
                onClick={() => setLayoutMode('4')}
                title="4-Column Side-by-Side View (Best for 9:16 vertical)"
              >
                <Columns4 size={13} />
                <span>4 Cols</span>
              </button>
              <button
                type="button"
                className={`baseline-toggle-btn ${effectiveColumns === 2 ? 'active' : ''}`}
                onClick={() => setLayoutMode('2')}
                title="2x2 Quadrant Grid View"
              >
                <LayoutGrid size={13} />
                <span>2×2 Grid</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Dynamic Candidate Grid */}
      <div
        className={`baseline-grid baseline-grid-${effectiveColumns} ratio-${currentRatioInfo.orientation}`}
      >
        {baselines.map((baseline, index) => {
          const isSelected = baseline.id === (selectedBaselineId || activeBaseline?.id);
          const itemRatio = parseAspectRatio(baseline.aspect_ratio || activeRatioStr);

          return (
            <div
              key={baseline.id}
              className={`baseline-card ${isSelected ? 'baseline-card-selected' : ''}`}
              onClick={() => onSelectBaseline && onSelectBaseline(baseline)}
            >
              <div
                className="baseline-image-wrapper"
                style={{ aspectRatio: itemRatio.cssRatio }}
              >
                <img
                  src={baseline.image_url}
                  alt={`Baseline candidate #${index + 1}`}
                  className="baseline-image"
                  style={{ objectFit: fitMode }}
                  loading="lazy"
                />

                <div className="baseline-overlay">
                  <button
                    type="button"
                    className="baseline-preview-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setZoomedImage({
                        url: baseline.image_url,
                        seed: baseline.seed,
                        index: index + 1,
                        aspectRatio: itemRatio.label,
                        prompt: baseline.compiled_prompt || baseline.prompt,
                      });
                    }}
                    title="Zoom Preview (Uncropped 100%)"
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

      {/* Zoom Modal - Uncropped High-Res Preview */}
      {zoomedImage && (
        <div
          className="modal-backdrop"
          onClick={() => setZoomedImage(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className="modal-content-zoom" onClick={(e) => e.stopPropagation()}>
            <div className="modal-zoom-header">
              <div className="modal-zoom-meta">
                <span className="modal-zoom-badge">
                  Candidate {zoomedImage.index ? `#${zoomedImage.index}` : ''} • Seed #{zoomedImage.seed || 'N/A'}
                </span>
                {zoomedImage.aspectRatio && (
                  <span className="modal-zoom-ratio-pill">
                    {zoomedImage.aspectRatio}
                  </span>
                )}
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setZoomedImage(null)}
                title="Close (Esc)"
                aria-label="Close (Esc)"
              >
                ×
              </button>
            </div>

            <div className="modal-zoom-body">
              <img
                src={zoomedImage.url || zoomedImage}
                alt="Zoomed baseline preview"
                className="zoomed-image"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
