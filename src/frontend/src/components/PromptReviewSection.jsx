import React, { useState, useMemo } from 'react';
import {
  Sparkles,
  Terminal,
  Copy,
  Check,
  RotateCcw,
  Plus,
  X,
  Layers,
  FileText,
  Loader2,
  Ratio,
  ArrowRight,
  Sliders,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Search,
  Info,
} from 'lucide-react';
import TagChip from './TagChip';
import { CATEGORIES } from '../utils/defaultTags';

const ASPECT_RATIO_RESOLUTIONS = {
  '1:1': '3840x3840',
  '16:9': '3840x2160',
  '9:16': '2160x3840',
  '21:9': '3840x1645',
  '2:3': '2560x3840',
  '3:2': '3840x2560',
  '4:5': '3072x3840',
  '5:4': '3840x3072',
  '3:4': '2880x3840',
  '4:3': '3840x2880',
  '1.8:1': '3840x2133',
  '1.85:1': '3840x2075',
};

const DEFAULT_NEGATIVE_PROMPT =
  'plastic skin, 3d render, cg, oversaturated, text, watermark, signature, blurry, low quality, deformed, extra limbs, bad anatomy, cartoon, drawing, painting, smoothing, airbrushing, mannequin, doll-like skin, plastic sheen, wax figure, oversmoothed facial features';

export default function PromptReviewSection({
  tagState = {},
  onUpdateTagState,
  masterPrompt = '',
  onMasterPromptChange,
  narrative = '',
  onNarrativeChange,
  aspectRatio = '1.8:1',
  temperature = 1.0,
  onTemperatureChange,
  conflicts = [],
  isCheckingConflicts = false,
  onCheckConflicts,
  isResyncing = false,
  isResyncingPrompt = false,
  onResyncPromptFromLevers,
  isResyncingLevers = false,
  onResyncLeversFromPrompt,
  onResyncPrompt,
  isGeneratingBaselines = false,
  onGenerateBaselines,
  hasBaselines = false,
}) {
  const effectiveIsResyncingPrompt = isResyncingPrompt || (isResyncing && !isResyncingLevers);
  const effectiveIsResyncingLevers = isResyncingLevers;
  const effectiveOnResyncPromptFromLevers = onResyncPromptFromLevers || onResyncPrompt;
  const effectiveOnResyncLeversFromPrompt = onResyncLeversFromPrompt;
  const isAnyResyncing = isResyncing || effectiveIsResyncingPrompt || effectiveIsResyncingLevers;

  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedFullPrompt, setCopiedFullPrompt] = useState(false);
  const [isPromptPreviewExpanded, setIsPromptPreviewExpanded] = useState(true);
  const [newTagInputs, setNewTagInputs] = useState({});
  const [activeAddCategory, setActiveAddCategory] = useState(null);
  const [isSectionExpanded, setIsSectionExpanded] = useState(true);

  const categories = tagState.categories || {};

  const conflictedTagsMap = useMemo(() => {
    const map = new Map();
    if (!conflicts || conflicts.length === 0) return map;
    conflicts.forEach((c) => {
      (c.conflicting_elements || []).forEach((el) => {
        const clean = String(el).toLowerCase().trim();
        if (clean) {
          map.set(clean, c);
        }
      });
    });
    return map;
  }, [conflicts]);

  const checkChipConflicted = (label) => {
    if (!label || conflictedTagsMap.size === 0) return { isConflicted: false, reason: '' };
    const cleanLabel = String(label).toLowerCase().trim();
    for (const [conflictedKey, conflictObj] of conflictedTagsMap.entries()) {
      if (cleanLabel.includes(conflictedKey) || conflictedKey.includes(cleanLabel)) {
        return { isConflicted: true, reason: conflictObj.explanation || 'Conflicting directive' };
      }
    }
    return { isConflicted: false, reason: '' };
  };

  const handleCopyPrompt = async () => {
    if (!masterPrompt) return;
    try {
      await navigator.clipboard.writeText(masterPrompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    } catch (err) {
      console.error('Failed to copy prompt to clipboard', err);
    }
  };

  const targetResolution = ASPECT_RATIO_RESOLUTIONS[aspectRatio] || '3840x2133';
  const fullPromptPreview = `${(masterPrompt || '').trim()} Resolution: ${targetResolution} (Aspect ratio: ${aspectRatio}). Temperature: ${(Number(temperature) || 1.0).toFixed(2)}. 600 DPI ultra-high-resolution print quality. Seed: [Candidate Seed #1..4]. Do not include: ${DEFAULT_NEGATIVE_PROMPT}.`;

  const handleCopyFullPrompt = async () => {
    try {
      await navigator.clipboard.writeText(fullPromptPreview);
      setCopiedFullPrompt(true);
      setTimeout(() => setCopiedFullPrompt(false), 2000);
    } catch (err) {
      console.error('Failed to copy full prompt to clipboard', err);
    }
  };

  const handleUpdateChip = (catKey, chipId, updates) => {
    const currentList = categories[catKey] || [];
    const updatedList = currentList.map((chip) => {
      if (chip.id === chipId) {
        return { ...chip, ...updates };
      }
      return chip;
    });

    onUpdateTagState({
      ...tagState,
      categories: {
        ...categories,
        [catKey]: updatedList,
      },
    });
  };

  const handleDeleteChip = (catKey, chipId) => {
    const currentList = categories[catKey] || [];
    const updatedList = currentList.filter((chip) => chip.id !== chipId);

    onUpdateTagState({
      ...tagState,
      categories: {
        ...categories,
        [catKey]: updatedList,
      },
    });
  };

  const handleAddTagSubmit = (catKey) => {
    const val = (newTagInputs[catKey] || '').trim();
    if (!val) {
      setActiveAddCategory(null);
      return;
    }

    const currentList = categories[catKey] || [];
    const newChip = {
      id: `tag_${catKey}_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
      category: catKey,
      label: val,
      enabled: true,
      locked: false,
      isCustom: true,
    };

    onUpdateTagState({
      ...tagState,
      categories: {
        ...categories,
        [catKey]: [...currentList, newChip],
      },
    });

    setNewTagInputs((prev) => ({ ...prev, [catKey]: '' }));
    setActiveAddCategory(null);
  };

  // Count total active tags
  const totalTagsCount = Object.values(categories).reduce((acc, list) => {
    return acc + (Array.isArray(list) ? list.length : 0);
  }, 0);

  const wordCount = masterPrompt.trim() ? masterPrompt.trim().split(/\s+/).length : 0;
  const charCount = masterPrompt.length;

  return (
    <div className="prompt-review-card">
      {/* Section Header */}
      <div className="prompt-review-header">
        <div className="prompt-review-title-group">
          <div className="prompt-review-badge">
            <Sparkles size={14} className="text-accent" />
            <span>Step 1B: Visual Direction & Prompt Review</span>
          </div>
          <h2 className="prompt-review-title">Director's Master Prompt & Visual Levers</h2>
          <p className="prompt-review-subtitle">
            Review the synthesized scene direction, customize individual visual levers, or edit the master prompt directly before generating 4 baseline image candidates. Click <strong>"Re-sync Master Prompt"</strong> to bidirectionally synchronize prompt prose and visual lever tags.
          </p>
        </div>

        <div className="prompt-review-meta-actions">
          <span className="prompt-tag-badge">
            {totalTagsCount} Levers • 9 Categories
          </span>
          <button
            type="button"
            className="btn-toggle-expand"
            onClick={() => setIsSectionExpanded(!isSectionExpanded)}
            title={isSectionExpanded ? 'Collapse Section' : 'Expand Section'}
          >
            {isSectionExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {isSectionExpanded && (
        <div className="prompt-review-body">
          {/* Conflict Warning Alert Box (Positioned above Master Prompt) */}
          {conflicts && conflicts.length > 0 && (
            <div className="prompt-conflict-alert-box" role="alert">
              <div className="prompt-conflict-header">
                <div className="prompt-conflict-title-group">
                  <div className="prompt-conflict-icon-wrap">
                    <AlertTriangle size={16} className="text-warning" />
                  </div>
                  <div>
                    <h3 className="prompt-conflict-title">
                      Contradictory Visual Directives Detected ({conflicts.length})
                    </h3>
                    <p className="prompt-conflict-subtitle">
                      The vision model identified conflicting instructions that will confuse the Imagen model or fight for scene dominance:
                    </p>
                  </div>
                </div>
                {onCheckConflicts && (
                  <button
                    type="button"
                    className="btn-recheck-conflicts"
                    onClick={onCheckConflicts}
                    disabled={isCheckingConflicts || isAnyResyncing}
                    title="Re-scan prompt and visual levers for conflicts"
                  >
                    {isCheckingConflicts ? (
                      <>
                        <Loader2 size={12} className="spin-animation" />
                        <span>Scanning...</span>
                      </>
                    ) : (
                      <>
                        <Search size={12} />
                        <span>Re-scan</span>
                      </>
                    )}
                  </button>
                )}
              </div>

              <div className="prompt-conflict-list">
                {conflicts.map((conflict, idx) => (
                  <div key={conflict.id || idx} className="prompt-conflict-item">
                    <div className="prompt-conflict-item-top">
                      <div className="prompt-conflict-elements">
                        {(conflict.conflicting_elements || []).map((elem, eIdx) => (
                          <React.Fragment key={eIdx}>
                            {eIdx > 0 && <span className="conflict-vs-tag">vs</span>}
                            <span className="conflict-element-chip">{elem}</span>
                          </React.Fragment>
                        ))}
                      </div>
                      {conflict.categories && conflict.categories.length > 0 && (
                        <div className="conflict-category-badges">
                          {conflict.categories.map((cat, cIdx) => (
                            <span key={cIdx} className="conflict-cat-badge">
                              {cat}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <p className="prompt-conflict-explanation">{conflict.explanation}</p>
                    {conflict.recommendation && (
                      <p className="prompt-conflict-recommendation">
                        <strong>Director Recommendation:</strong> {conflict.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Master Generation Prompt Textarea */}
          <div className="prompt-textarea-box">
            <div className="prompt-textarea-header">
              <div className="prompt-textarea-label-group">
                <Terminal size={14} className="text-accent" />
                <label htmlFor="master-prompt-textarea" className="prompt-textarea-label">
                  Vision Director Master Prompt (Direct Positive Generation Input)
                </label>
              </div>

              <div className="prompt-textarea-actions">
                {onCheckConflicts && (
                  <button
                    type="button"
                    className="btn-prompt-action btn-scan-conflicts"
                    onClick={onCheckConflicts}
                    disabled={isCheckingConflicts || isAnyResyncing || isGeneratingBaselines}
                    title="Scan current master prompt & visual levers for contradictions"
                  >
                    {isCheckingConflicts ? (
                      <>
                        <Loader2 size={12} className="spin-animation" />
                        <span>Checking Conflicts...</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle size={12} className={conflicts.length > 0 ? "text-warning" : ""} />
                        <span>Scan for Conflicts</span>
                      </>
                    )}
                  </button>
                )}

                {effectiveOnResyncLeversFromPrompt && (
                  <button
                    type="button"
                    className="btn-resync-levers"
                    onClick={effectiveOnResyncLeversFromPrompt}
                    disabled={effectiveIsResyncingLevers || isGeneratingBaselines || !masterPrompt.trim()}
                    title="Extract and update 9-category visual levers from this Master Prompt"
                  >
                    {effectiveIsResyncingLevers ? (
                      <>
                        <Loader2 size={13} className="spin-animation" />
                        <span>Extracting Levers...</span>
                      </>
                    ) : (
                      <>
                        <Sliders size={13} />
                        <span>Re-sync Levers from Prompt</span>
                      </>
                    )}
                  </button>
                )}

                <button
                  type="button"
                  className="btn-prompt-action"
                  onClick={handleCopyPrompt}
                  title="Copy Master Prompt"
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
              </div>
            </div>

            <textarea
              id="master-prompt-textarea"
              className="prompt-master-textarea"
              rows={4}
              value={masterPrompt}
              onChange={(e) => onMasterPromptChange && onMasterPromptChange(e.target.value)}
              placeholder="Evocative Master Generation Prompt synthesized from moodboard references..."
              disabled={isGeneratingBaselines || isAnyResyncing}
            />

            <div className="prompt-textarea-footer">
              <span className="prompt-stats-text">
                {wordCount} words • {charCount} chars
              </span>
              <span className="prompt-hint-text">
                * This exact prompt will be submitted to the image generation model alongside technical quality, target resolution, and seed directives.
              </span>
            </div>
          </div>

          {/* 9-Category Extracted Visual Levers Grid */}
          <div className="prompt-levers-section">
            <div className="prompt-levers-header">
              <div className="prompt-levers-header-top">
                <div className="prompt-levers-title-group">
                  <Layers size={14} className="text-accent" />
                  <span className="prompt-levers-title">Extracted 9-Category Visual Levers</span>
                </div>

                {effectiveOnResyncPromptFromLevers && (
                  <button
                    type="button"
                    className="btn-resync-prompt"
                    onClick={effectiveOnResyncPromptFromLevers}
                    disabled={effectiveIsResyncingPrompt || isGeneratingBaselines}
                    title="Re-synthesize Master Generation Prompt prose from active visual levers"
                  >
                    {effectiveIsResyncingPrompt ? (
                      <>
                        <Loader2 size={13} className="spin-animation" />
                        <span>Re-syncing Prompt...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles size={13} />
                        <span>Re-sync Master Prompt from Levers</span>
                      </>
                    )}
                  </button>
                )}
              </div>
              <span className="prompt-levers-subtitle">
                Click a tag to inline-edit, delete, or add new levers. After adjusting levers, click <strong>"Re-sync Master Prompt from Levers"</strong> to regenerate the master prompt above. Or edit the prompt directly and click <strong>"Re-sync Levers from Prompt"</strong> to extract updated tags.
              </span>
            </div>

            <div className="prompt-levers-grid">
              {CATEGORIES.map((cat) => {
                const tagList = categories[cat.key] || [];
                const isAdding = activeAddCategory === cat.key;

                return (
                  <div key={cat.key} className="prompt-category-card">
                    <div className="prompt-cat-header">
                      <div className="prompt-cat-title-group">
                        <span
                          className="prompt-cat-dot"
                          style={{ backgroundColor: cat.color }}
                        />
                        <span className="prompt-cat-name">{cat.label}</span>
                      </div>

                      <div className="prompt-cat-actions">
                        <span className="prompt-cat-count">{tagList.length}</span>
                        {!isAdding && (
                          <button
                            type="button"
                            className="btn-add-tag-trigger"
                            onClick={() => {
                              setActiveAddCategory(cat.key);
                              setNewTagInputs((prev) => ({ ...prev, [cat.key]: '' }));
                            }}
                            title={`Add tag to ${cat.label}`}
                          >
                            <Plus size={11} />
                            <span>Add</span>
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="prompt-cat-tags-wrap">
                      {tagList.map((chip) => {
                        const conflictInfo = checkChipConflicted(chip.label);
                        return (
                          <TagChip
                            key={chip.id}
                            chip={{
                              ...chip,
                              category: cat.key,
                            }}
                            isConflicted={conflictInfo.isConflicted}
                            conflictReason={conflictInfo.reason}
                            onUpdate={(id, updates) => handleUpdateChip(cat.key, id, updates)}
                            onDelete={(id) => handleDeleteChip(cat.key, id)}
                          />
                        );
                      })}

                      {tagList.length === 0 && !isAdding && (
                        <span className="prompt-cat-empty">No tags in this category</span>
                      )}

                      {/* Inline Add Tag Input */}
                      {isAdding && (
                        <div className="inline-add-tag-box">
                          <input
                            type="text"
                            autoFocus
                            className="inline-add-tag-input"
                            placeholder="Type tag & hit Enter..."
                            value={newTagInputs[cat.key] || ''}
                            onChange={(e) =>
                              setNewTagInputs((prev) => ({ ...prev, [cat.key]: e.target.value }))
                            }
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleAddTagSubmit(cat.key);
                              } else if (e.key === 'Escape') {
                                setActiveAddCategory(null);
                              }
                            }}
                          />
                          <button
                            type="button"
                            className="inline-add-tag-confirm"
                            onClick={() => handleAddTagSubmit(cat.key)}
                            title="Add Tag"
                          >
                            <Check size={11} />
                          </button>
                          <button
                            type="button"
                            className="inline-add-tag-cancel"
                            onClick={() => setActiveAddCategory(null)}
                            title="Cancel"
                          >
                            <X size={11} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Full Prompt Submitted to API (Baseline Generation Preview) */}
          <div className="baseline-prompt-panel" style={{ marginTop: '4px' }}>
            <div className="baseline-prompt-header">
              <div className="baseline-prompt-title-group">
                <Terminal size={14} className="text-accent" />
                <span className="baseline-prompt-title">
                  Full Prompt Submitted to API (Baseline Generation Preview)
                </span>
                <span className="baseline-prompt-tag">
                  {targetResolution} ({aspectRatio}) • Temp {(Number(temperature) || 1.0).toFixed(2)}
                </span>
              </div>

              <div className="baseline-prompt-actions">
                <button
                  type="button"
                  className="btn-prompt-action"
                  onClick={handleCopyFullPrompt}
                  title="Copy Full Assembled Generation Prompt"
                >
                  {copiedFullPrompt ? (
                    <>
                      <Check size={12} className="text-success" />
                      <span className="text-success">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy size={12} />
                      <span>Copy Full Prompt</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  className="btn-prompt-action"
                  onClick={() => setIsPromptPreviewExpanded(!isPromptPreviewExpanded)}
                  title={isPromptPreviewExpanded ? 'Collapse' : 'Expand'}
                >
                  {isPromptPreviewExpanded ? (
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

            <div className={`baseline-prompt-content ${isPromptPreviewExpanded ? 'expanded' : 'collapsed'}`}>
              {fullPromptPreview}
            </div>
          </div>

          {/* Primary Baseline Generation Action Bar */}
          <div className="prompt-action-bar">
            <div className="prompt-action-info">
              <div className="prompt-meta-controls">
                <div className="prompt-aspect-tag">
                  <Ratio size={14} className="text-accent" />
                  <span>
                    Aspect Ratio: <strong>{aspectRatio}</strong> ({targetResolution})
                  </span>
                </div>

                {/* Step 1 Temperature Slider Control */}
                <div className="prompt-temp-control" title="Generation Temperature: Controls creative randomness across 4 candidate seeds. Lower = Strict / Deterministic, Higher = Creative Variance.">
                  <div className="prompt-temp-header">
                    <SlidersHorizontal size={13} className="text-accent" />
                    <span className="prompt-temp-label">
                      Temperature: <strong className="prompt-temp-val">{(Number(temperature) || 1.0).toFixed(2)}</strong>
                    </span>
                    <span className="prompt-temp-hint">
                      {temperature < 0.6
                        ? 'Strict Fidelity'
                        : temperature > 1.3
                        ? 'High Variance'
                        : 'Balanced Editorial'}
                    </span>
                  </div>
                  <input
                    type="range"
                    id="step1-temperature-slider"
                    aria-label="Seed generation temperature"
                    min="0.0"
                    max="2.0"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => onTemperatureChange && onTemperatureChange(parseFloat(e.target.value))}
                    className="prompt-temp-slider"
                    disabled={isGeneratingBaselines || isAnyResyncing}
                  />
                </div>
              </div>

              <span className="prompt-action-note">
                Renders 4 unique baseline candidates across 4 distinct seeds concurrently at {targetResolution} (Temp {(Number(temperature) || 1.0).toFixed(2)}).
              </span>
            </div>

            <button
              type="button"
              className="btn-primary btn-generate-baselines"
              onClick={onGenerateBaselines}
              disabled={isGeneratingBaselines || isAnyResyncing || !masterPrompt.trim()}
            >
              {isGeneratingBaselines ? (
                <>
                  <Loader2 size={16} className="spin-animation" />
                  <span>Rendering 4 Baseline Seeds...</span>
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  <span>
                    {hasBaselines
                      ? 'Re-generate 4 Baselines'
                      : 'Generate 4 Baseline Candidates'}
                  </span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

