import React, { useState } from 'react';
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
  ChevronDown,
  ChevronUp,
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
  isResyncing = false,
  onResyncPrompt,
  isGeneratingBaselines = false,
  onGenerateBaselines,
  hasBaselines = false,
}) {
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedFullPrompt, setCopiedFullPrompt] = useState(false);
  const [isPromptPreviewExpanded, setIsPromptPreviewExpanded] = useState(true);
  const [newTagInputs, setNewTagInputs] = useState({});
  const [activeAddCategory, setActiveAddCategory] = useState(null);
  const [isSectionExpanded, setIsSectionExpanded] = useState(true);

  const categories = tagState.categories || {};

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
  const fullPromptPreview = `${(masterPrompt || '').trim()} Resolution: ${targetResolution} (Aspect ratio: ${aspectRatio}). 600 DPI ultra-high-resolution print quality. Seed: [Candidate Seed #1..4]. Do not include: ${DEFAULT_NEGATIVE_PROMPT}.`;

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
            Review the synthesized scene direction, customize individual visual levers, or edit the master prompt directly before generating 4 baseline image candidates.
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
          {/* Scene Narrative Box */}
          <div className="prompt-narrative-box">
            <div className="prompt-narrative-header">
              <div className="prompt-narrative-label-group">
                <FileText size={13} className="text-accent" />
                <label htmlFor="scene-narrative-input" className="prompt-narrative-label">
                  Scene Narrative & Core Logline
                </label>
              </div>
            </div>
            <input
              id="scene-narrative-input"
              type="text"
              className="prompt-narrative-input"
              value={narrative}
              onChange={(e) => onNarrativeChange && onNarrativeChange(e.target.value)}
              placeholder="1-2 sentence core creative scene logline..."
              disabled={isGeneratingBaselines || isResyncing}
            />
          </div>

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
                <button
                  type="button"
                  className="btn-resync-prompt"
                  onClick={onResyncPrompt}
                  disabled={isResyncing || isGeneratingBaselines}
                  title="Re-synthesize high-fashion directorial prose from the updated visual lever tags below"
                >
                  {isResyncing ? (
                    <>
                      <Loader2 size={13} className="spin-animation" />
                      <span>Re-syncing with AI...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={13} />
                      <span>Re-sync Master Prompt</span>
                    </>
                  )}
                </button>

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
              disabled={isGeneratingBaselines || isResyncing}
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
              <div className="prompt-levers-title-group">
                <Layers size={14} className="text-accent" />
                <span className="prompt-levers-title">Extracted 9-Category Visual Levers</span>
              </div>
              <span className="prompt-levers-subtitle">
                Click tag to inline-edit, delete, or add new levers. Click <strong>"Re-sync Master Prompt"</strong> above to integrate edits into prose.
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
                      {tagList.map((chip) => (
                        <TagChip
                          key={chip.id}
                          chip={{
                            ...chip,
                            category: cat.key,
                          }}
                          onUpdate={(id, updates) => handleUpdateChip(cat.key, id, updates)}
                          onDelete={(id) => handleDeleteChip(cat.key, id)}
                        />
                      ))}

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
                  {targetResolution} ({aspectRatio})
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
              <div className="prompt-aspect-tag">
                <Ratio size={14} className="text-accent" />
                <span>
                  Aspect Ratio: <strong>{aspectRatio}</strong> ({targetResolution})
                </span>
              </div>
              <span className="prompt-action-note">
                Renders 4 unique baseline candidates across 4 distinct seeds concurrently at {targetResolution}.
              </span>
            </div>

            <button
              type="button"
              className="btn-primary btn-generate-baselines"
              onClick={onGenerateBaselines}
              disabled={isGeneratingBaselines || isResyncing || !masterPrompt.trim()}
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
