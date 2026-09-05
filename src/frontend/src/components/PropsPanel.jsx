import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Upload,
  Layers,
  Sparkles,
  Trash2,
  AlertCircle,
  Eye,
  Info,
  HelpCircle,
  Send,
  Sliders,
  Box,
  Plus,
} from 'lucide-react';
import {
  uploadPropSheet,
  uploadSingleProp,
  fetchPropItems,
  deletePropItem,
  deleteAllPropItems,
} from '../services/apiClient';
import { formatSpendSGD } from '../utils/formatters';
import { PROP_CATEGORIES, PROP_CATEGORY_COLORS, PROP_SCALE_PRESETS } from '../constants/propCategories';
import PropPreviewModal from './PropPreviewModal';

export default function PropsPanel({
  isOpen = false,
  onClose,
  assignments = [],
  onAddAssignment,
  onRemoveAssignment,
  onClearAssignments,
  onUpdatePropScale,
  onUpdatePropNotes,
  onCompose,
  isComposing = false,
  activeGenerationId = null,
  visionModel = null,
}) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [customInstruction, setCustomInstruction] = useState('');
  const [previewItemId, setPreviewItemId] = useState(null);
  const [uploadMode, setUploadMode] = useState('sheet'); // 'sheet' | 'single'
  const [singleCategory, setSingleCategory] = useState('decor');

  const fileInputRef = useRef(null);

  // Load prop library items on mount or when panel opens
  useEffect(() => {
    if (isOpen) {
      loadItems();
    }
  }, [isOpen]);

  // Auto-poll while any props are pending or processing AI detail upscaling
  useEffect(() => {
    if (!isOpen) return;
    const hasPendingUpscale = items.some(
      (item) => item.upscale_status === 'pending' || item.upscale_status === 'processing'
    );
    if (!hasPendingUpscale) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetchPropItems();
        if (res.items) {
          setItems(res.items);
        }
      } catch (err) {
        console.warn('Failed to poll prop items status:', err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [isOpen, items]);

  const loadItems = async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const res = await fetchPropItems();
      setItems(res.items || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load prop library.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    try {
      setIsUploading(true);
      setErrorMessage(null);

      let res;
      if (uploadMode === 'single') {
        res = await uploadSingleProp(file, singleCategory, visionModel);
      } else {
        res = await uploadPropSheet(file, visionModel);
      }

      if (res.items && res.items.length > 0) {
        setItems((prev) => [...res.items, ...prev]);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to upload and process prop.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteItem = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Remove this prop from your library?')) return;
    try {
      await deletePropItem(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      if (previewItemId === id) {
        setPreviewItemId(null);
      }
      assignments.forEach((asgn) => {
        if (asgn.prop_item_id === id) {
          onRemoveAssignment?.(asgn.pin_number);
        }
      });
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete prop.');
    }
  };

  const handleDeleteAll = async () => {
    if (items.length === 0) return;
    if (!window.confirm(`Delete all ${items.length} props from your library?`)) return;
    try {
      setIsLoading(true);
      await deleteAllPropItems();
      setItems([]);
      setPreviewItemId(null);
      onClearAssignments?.();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete all props.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDragStart = (e, item) => {
    e.dataTransfer.setData('application/json', JSON.stringify({ ...item, isProp: true }));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleQuickAdd = (item) => {
    onAddAssignment?.(item, { x: 0.5, y: 0.5 });
  };

  const filteredItems = selectedCategory === 'all'
    ? items
    : items.filter((item) => (item.category || 'decor').toLowerCase() === selectedCategory);

  if (!isOpen) return null;

  return (
    <aside className="wardrobe-panel-container" aria-label="Prop Library Panel">
      {/* Header */}
      <div className="wardrobe-panel-header">
        <div className="wardrobe-header-title-row">
          <div className="wardrobe-title-badge">
            <Box size={16} className="text-accent" />
            <span>Props Studio</span>
          </div>
          <div className="wardrobe-header-actions">
            <span className="wardrobe-count-badge">
              {items.length} prop{items.length !== 1 ? 's' : ''}
            </span>
            {items.length > 0 && (
              <button
                type="button"
                className="btn-text-danger"
                onClick={handleDeleteAll}
                title="Delete all props from library"
                aria-label="Delete all props"
              >
                <Trash2 size={12} />
                <span>Delete All</span>
              </button>
            )}
            <button
              type="button"
              className="btn-icon-subtle"
              onClick={onClose}
              title="Close props panel"
              aria-label="Close Props Studio"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        <p className="wardrobe-subtitle">
          Upload catalog sheets or single props. Drag items onto the canvas and scale them to place seamlessly.
        </p>
      </div>

      {/* Dual Upload Mode Selector */}
      <div className="props-upload-mode-container">
        <div className="props-upload-mode-toggle" role="group" aria-label="Upload Mode">
          <button
            type="button"
            className={`props-upload-mode-btn ${uploadMode === 'sheet' ? 'active' : ''}`}
            onClick={() => setUploadMode('sheet')}
          >
            Multi-Prop Catalog Sheet
          </button>
          <button
            type="button"
            className={`props-upload-mode-btn ${uploadMode === 'single' ? 'active' : ''}`}
            onClick={() => setUploadMode('single')}
          >
            Single Isolated Prop
          </button>
        </div>

        {uploadMode === 'single' && (
          <div className="props-category-select-row">
            <span className="props-category-select-label">
              Category:
            </span>
            <select
              value={singleCategory}
              onChange={(e) => setSingleCategory(e.target.value)}
              className="app-select props-category-dropdown"
            >
              {PROP_CATEGORIES.filter((c) => c !== 'all').map((cat) => (
                <option key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Upload Zone */}
      <div className="wardrobe-upload-section" style={{ paddingTop: '0.25rem' }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileUpload}
          aria-label="Upload prop image"
        />
        <div
          className={`wardrobe-dropzone ${isUploading ? 'is-uploading' : ''}`}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          aria-label={uploadMode === 'single' ? 'Click to upload single prop' : 'Click to upload prop catalog sheet'}
        >
          {isUploading ? (
            <div className="wardrobe-uploading-spinner-row" role="status" aria-live="polite">
              <div className="generating-spinner" />
              <div className="upload-text-group">
                <span className="upload-main-text">
                  {uploadMode === 'single' ? 'Analyzing Prop Features...' : 'Analyzing & Segmenting Sheet...'}
                </span>
                <span className="upload-sub-text">
                  {uploadMode === 'single' ? 'Extracting materials and finish' : 'Gemini Vision detecting bounding boxes'}
                </span>
              </div>
            </div>
          ) : (
            <div className="wardrobe-dropzone-inner">
              <div className="dropzone-icon-circle">
                <Upload size={16} />
              </div>
              <div className="upload-text-group">
                <span className="upload-main-text">
                  {uploadMode === 'single' ? 'Upload Single Prop Image' : 'Upload Multi-Prop Catalog Sheet'}
                </span>
                <span className="upload-sub-text">
                  {uploadMode === 'single' ? 'Auto-extracts material & finish' : 'Auto-segments into individual items'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="wardrobe-error-banner" role="alert">
          <AlertCircle size={14} />
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} aria-label="Dismiss error">
            <X size={12} />
          </button>
        </div>
      )}

      {/* Category Pills */}
      <div className="wardrobe-category-bar" role="tablist" aria-label="Prop categories">
        {PROP_CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            role="tab"
            className={`category-pill ${selectedCategory === cat ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
            style={
              selectedCategory === cat && cat !== 'all'
                ? { borderColor: PROP_CATEGORY_COLORS[cat] || 'var(--accent-primary)', color: PROP_CATEGORY_COLORS[cat] || 'var(--accent-primary)' }
                : {}
            }
            aria-selected={selectedCategory === cat}
          >
            {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {/* Items Grid */}
      <div className="wardrobe-items-scroll wardrobe-items-container" tabIndex={0} role="region" aria-label="Prop Library Items">
        {isLoading ? (
          <div className="wardrobe-loading-grid">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="garment-card-skeleton" />
            ))}
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="gallery-empty-state props-empty-state" role="status">
            <div className="empty-icon-capsule">
              <Box size={22} className="empty-capsule-icon" />
            </div>
            <h4 className="empty-title">
              {items.length === 0
                ? 'No Props in Studio Library'
                : `No ${selectedCategory.charAt(0).toUpperCase() + selectedCategory.slice(1)} Props`}
            </h4>
            <p className="empty-desc">
              {items.length === 0
                ? 'Upload a multi-prop catalog sheet or single isolated prop above to curate your scene.'
                : `No props found in this category. You have ${items.length} prop${items.length === 1 ? '' : 's'} in other categories.`}
            </p>
            <div className="empty-actions-row">
              {items.length === 0 ? (
                <button
                  type="button"
                  className="btn-gallery-empty-action"
                  onClick={() => !isUploading && fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  <Upload size={13} />
                  <span>{uploadMode === 'single' ? 'Upload Prop Image' : 'Upload Catalog Sheet'}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-gallery-empty-action"
                  onClick={() => setSelectedCategory('all')}
                >
                  <span>View All Props ({items.length})</span>
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="wardrobe-items-grid">
            {filteredItems.map((item) => {
              const catColor = PROP_CATEGORY_COLORS[item.category] || PROP_CATEGORY_COLORS.decor;
              const isUpscaled = item.is_upscaled || item.upscale_status === 'completed';
              const isProcessing = item.upscale_status === 'processing';
              const displayImage = item.upscaled_image_url || item.image_url;

              return (
                <div
                  key={item.id}
                  className="garment-card"
                  draggable
                  onDragStart={(e) => handleDragStart(e, item)}
                  onClick={() => handleQuickAdd(item)}
                  title="Drag onto scene image or click to place"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleQuickAdd(item);
                    }
                  }}
                  role="button"
                  aria-label={`${item.label}, Category: ${item.category || 'decor'}${isUpscaled ? ', 4K Enhanced' : ''}`}
                >
                  <div className="garment-thumbnail-box">
                    <img
                      src={displayImage}
                      alt={item.label || 'Prop'}
                      className="garment-thumb-img"
                      loading="lazy"
                    />
                    {isUpscaled && (
                      <div className="garment-hd-tag" title="4K AI Enhanced">
                        <Sparkles size={9} />
                        <span>4K</span>
                      </div>
                    )}
                    {isProcessing && (
                      <div className="garment-processing-tag" title="Upscaling in background...">
                        <div className="generating-spinner" style={{ width: 8, height: 8 }} />
                        <span>Upscaling</span>
                      </div>
                    )}
                    {(item.cost_usd > 0 || item.cost_sgd > 0) && (
                      <div className="garment-cost-badge" title="Compute Spend">
                        <span>{formatSpendSGD(item.cost_sgd, item.cost_usd)}</span>
                      </div>
                    )}
                  </div>
                  <div className="garment-info-row">
                    <div className="garment-text-col">
                      <span className="garment-title" title={item.label}>
                        {item.label}
                      </span>
                      <div className="garment-tags-wrap">
                        <span
                          className="garment-cat-tag"
                          style={{ color: catColor, borderColor: `${catColor}40` }}
                        >
                          {item.category || 'decor'}
                        </span>
                        {item.extracted_details?.material_finish && (
                          <span
                            className="garment-feature-tag tag-cyan"
                            title={`Material: ${item.extracted_details.material_finish}`}
                          >
                            {item.extracted_details.material_finish.split(',')[0]}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="garment-card-actions">
                      <button
                        type="button"
                        className="garment-action-btn garment-preview-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPreviewItemId(item.id);
                        }}
                        title="Preview & inspect prop quality"
                        aria-label={`Preview quality of ${item.label}`}
                      >
                        <Eye size={12} />
                      </button>
                      <button
                        type="button"
                        className="garment-action-btn garment-delete-btn"
                        onClick={(e) => handleDeleteItem(e, item.id)}
                        title="Delete prop"
                        aria-label={`Delete ${item.label}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Queued Placements & Composition Bar */}
      <div className="wardrobe-assignments-footer">
        <div className="assignments-header-row">
          <div className="assignments-title-group">
            <Layers size={14} className="text-accent" />
            <span className="assignments-title">Queued Props ({assignments.length})</span>
          </div>
          {assignments.length > 0 && (
            <button
              type="button"
              className="btn-text-subtle"
              onClick={onClearAssignments}
              disabled={isComposing}
              aria-label="Clear all prop assignments"
            >
              Clear All
            </button>
          )}
        </div>

        {assignments.length === 0 ? (
          <div className="assignments-empty-hint">
            <HelpCircle size={13} className="text-muted" />
            <span>Drag a prop above and drop onto the scene image, or click to place.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '180px', overflowY: 'auto', paddingRight: '0.25rem' }}>
            {assignments.map((asgn) => (
              <div
                key={asgn.pin_number}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.45rem 0.6rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.35rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 }}>
                    <span className="assignment-pin-num" style={{ background: '#14b8a6', color: '#fff' }}>
                      #{asgn.pin_number}
                    </span>
                    <span className="assignment-item-label" style={{ fontWeight: 600, fontSize: '0.78rem' }}>
                      {asgn.item_label || 'Prop'}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="assignment-remove-btn"
                    onClick={() => onRemoveAssignment?.(asgn.pin_number)}
                    title="Remove this prop"
                    aria-label={`Remove #${asgn.pin_number}`}
                  >
                    <X size={12} />
                  </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Scale:</span>
                  <div className="props-scale-toggle" style={{ flex: 1 }}>
                    {PROP_SCALE_PRESETS.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        className={`props-scale-btn ${(asgn.scale_preset || 'medium') === preset.id ? 'active' : ''}`}
                        onClick={() => onUpdatePropScale?.(asgn.pin_number, preset.id)}
                        title={preset.description}
                      >
                        {preset.label.split(' ')[0]}
                      </button>
                    ))}
                  </div>
                </div>

                <input
                  type="text"
                  placeholder="Notes (e.g., place on wooden table, soft shadows)"
                  value={asgn.notes || ''}
                  onChange={(e) => onUpdatePropNotes?.(asgn.pin_number, e.target.value)}
                  style={{
                    fontSize: '0.72rem',
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-xs)',
                    padding: '0.2rem 0.4rem',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {/* Custom Direction Input */}
        <div className="wardrobe-instruction-wrap" style={{ marginTop: '0.5rem' }}>
          <input
            type="text"
            className="wardrobe-instruction-input"
            placeholder="Scene instruction (e.g. realistic reflections, ground on marble)"
            value={customInstruction}
            onChange={(e) => setCustomInstruction(e.target.value)}
            disabled={isComposing || assignments.length === 0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && assignments.length > 0) {
                onCompose?.(customInstruction);
              }
            }}
          />
        </div>

        {/* Action Button */}
        <button
          type="button"
          className="btn-primary w-full wardrobe-compose-btn"
          onClick={() => onCompose?.(customInstruction)}
          disabled={assignments.length === 0 || isComposing}
          aria-label="Compose scene with props"
        >
          {isComposing ? (
            <>
              <div className="generating-spinner" />
              <span>Grounding & Composing Props...</span>
            </>
          ) : (
            <>
              <Sparkles size={15} />
              <span>
                Compose Props ({assignments.length})
              </span>
            </>
          )}
        </button>
      </div>

      {/* Quality Preview & Inspector Modal */}
      {previewItemId && (
        <PropPreviewModal
          isOpen={Boolean(previewItemId)}
          onClose={() => setPreviewItemId(null)}
          items={items}
          initialItemId={previewItemId}
          onAddAssignment={onAddAssignment}
          onDeleteItem={handleDeleteItem}
          onUpdateItem={(updated) => {
            setItems((prev) =>
              prev.map((it) => (it.id === updated.id ? { ...it, ...updated } : it))
            );
          }}
        />
      )}
    </aside>
  );
}
