import React, { useState } from 'react';
import {
  History,
  X,
  RotateCcw,
  GitBranch,
  Split,
  Hash,
  Clock,
  Sparkles,
  Layers,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Terminal,
  Eye,
  Crosshair,
} from 'lucide-react';

export default function HistoryDrawer({
  isOpen = false,
  onClose,
  history = [],
  activeGenerationId,
  onRestoreGeneration,
  selectedForCompare = [],
  onToggleCompare,
  onOpenCompareModal,
}) {
  const [expandedPromptIds, setExpandedPromptIds] = useState([]);
  const [copiedId, setCopiedId] = useState(null);
  const [viewingMaskId, setViewingMaskId] = useState(null);

  if (!isOpen) return null;

  const togglePromptExpanded = (id) => {
    setExpandedPromptIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleCopy = async (id, promptText) => {
    if (!promptText) return;
    try {
      await navigator.clipboard.writeText(promptText);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy prompt to clipboard', err);
    }
  };

  return (
    <div className="history-drawer-overlay" onClick={onClose}>
      <div className="history-drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="history-header">
          <div className="history-title-group">
            <History size={18} className="text-accent" />
            <span className="history-title">Generation Lineage & History</span>
            <span className="history-badge">{history.length} records</span>
          </div>

          <button type="button" className="history-close-btn" onClick={onClose} title="Close History">
            <X size={18} />
          </button>
        </div>

        {/* Compare Toolbar if items selected */}
        {selectedForCompare.length > 0 && (
          <div className="history-compare-bar">
            <span>{selectedForCompare.length}/2 selected for comparison</span>
            {selectedForCompare.length === 2 && (
              <button
                type="button"
                className="btn-primary btn-sm"
                onClick={onOpenCompareModal}
              >
                <Split size={14} />
                <span>Launch Split-Slider Diff</span>
              </button>
            )}
          </div>
        )}

        {/* History List */}
        <div className="history-list">
          {history.length === 0 ? (
            <div className="history-empty-state">
              <Sparkles size={24} className="text-muted" />
              <p>No generations created yet. Generate a baseline to start building lineage history.</p>
            </div>
          ) : (
            history.map((item) => {
              const isActive = item.id === activeGenerationId;
              const isCheckedForCompare = selectedForCompare.includes(item.id);
              const isExpanded = expandedPromptIds.includes(item.id);
              const fullPromptText = item.compiled_prompt || item.prompt || '';
              const isCopied = copiedId === item.id;

              const inpaintMeta = item.inpaint_metadata || item.schema_json?.inpaint_metadata;
              const isInpaint = item.id?.startsWith('gen_inpaint_') || fullPromptText.startsWith('[Inpaint') || Boolean(inpaintMeta);
              const maskUrl = item.mask_image_url || inpaintMeta?.mask_url;
              const maskCoverage = inpaintMeta?.mask_stats?.coverage_percentage;
              const isShowingMask = viewingMaskId === item.id && Boolean(maskUrl);

              return (
                <div
                  key={item.id}
                  className={`history-card ${isActive ? 'history-card-active' : ''} ${isCheckedForCompare ? 'history-card-compare' : ''}`}
                >
                  <div className="history-card-thumb-wrapper">
                    <img
                      src={isShowingMask ? maskUrl : (item.master_image_url || item.image_url)}
                      alt={isShowingMask ? `Mask for ${item.id}` : `Generation ${item.id}`}
                      className="history-card-thumb"
                    />
                    {item.is_baseline ? (
                      <span className="history-type-tag baseline-tag">
                        <Layers size={10} />
                        <span>Baseline</span>
                      </span>
                    ) : isInpaint ? (
                      <span className="history-type-tag inpaint-tag" title={maskCoverage !== undefined ? `Mask Coverage: ${maskCoverage}%` : 'Targeted Inpaint Edit'}>
                        <Crosshair size={10} />
                        <span>Inpaint{maskCoverage !== undefined ? ` (${maskCoverage}%)` : ''}</span>
                      </span>
                    ) : (
                      <span className="history-type-tag child-tag">
                        <GitBranch size={10} />
                        <span>Iteration</span>
                      </span>
                    )}
                  </div>

                  <div className="history-card-content">
                    <div className="history-card-meta">
                      <span className="history-card-seed">
                        <Hash size={11} />
                        <span>Seed #{item.seed}</span>
                      </span>
                      <span className="history-card-time">
                        <Clock size={11} />
                        <span>{item.created_at ? new Date(item.created_at).toLocaleTimeString() : ''}</span>
                      </span>
                      {maskCoverage !== undefined && (
                        <span className="history-card-mask-stat" title={`Masked area covers ${maskCoverage}% of the canvas`}>
                          Area: {maskCoverage}%
                        </span>
                      )}
                    </div>

                    <div className="history-prompt-block">
                      <p className={`history-card-prompt ${isExpanded ? 'expanded' : ''}`} title={fullPromptText}>
                        {fullPromptText || 'Structured scene generation'}
                      </p>

                      {fullPromptText && (
                        <div className="history-prompt-ctrls">
                          <button
                            type="button"
                            className="history-prompt-btn"
                            onClick={() => handleCopy(item.id, fullPromptText)}
                            title="Copy full prompt"
                          >
                            {isCopied ? (
                              <>
                                <Check size={10} className="text-success" />
                                <span className="text-success">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy size={10} />
                                <span>Copy Prompt</span>
                              </>
                            )}
                          </button>

                          {maskUrl && (
                            <button
                              type="button"
                              className={`history-prompt-btn ${isShowingMask ? 'history-prompt-btn-active' : ''}`}
                              onClick={() => setViewingMaskId(isShowingMask ? null : item.id)}
                              title="Toggle Inpaint Mask Map"
                            >
                              <Eye size={10} />
                              <span>{isShowingMask ? 'Show Image' : 'Show Mask'}</span>
                            </button>
                          )}

                          <button
                            type="button"
                            className="history-prompt-btn"
                            onClick={() => togglePromptExpanded(item.id)}
                            title={isExpanded ? 'Collapse prompt' : 'Expand full prompt'}
                          >
                            {isExpanded ? (
                              <>
                                <ChevronUp size={10} />
                                <span>Less</span>
                              </>
                            ) : (
                              <>
                                <ChevronDown size={10} />
                                <span>Full Prompt</span>
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="history-card-actions">
                      <button
                        type="button"
                        className="btn-secondary btn-xs"
                        onClick={() => onRestoreGeneration && onRestoreGeneration(item)}
                        title="Restore parameters and canvas state"
                      >
                        <RotateCcw size={12} />
                        <span>Restore State</span>
                      </button>

                      <label className="history-compare-checkbox">
                        <input
                          type="checkbox"
                          checked={isCheckedForCompare}
                          disabled={!isCheckedForCompare && selectedForCompare.length >= 2}
                          onChange={() => onToggleCompare && onToggleCompare(item.id)}
                        />
                        <span>Compare</span>
                      </label>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

