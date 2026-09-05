import React, { useState, useRef, useEffect } from 'react';
import {
  Shirt,
  Upload,
  Sparkles,
  Trash2,
  X,
  Layers,
  CheckCircle2,
  AlertCircle,
  Tag,
  GripHorizontal,
  RefreshCw,
  HelpCircle,
  Eye,
} from 'lucide-react';
import { uploadWardrobeSheet, fetchWardrobeItems, deleteWardrobeItem, deleteAllWardrobeItems } from '../services/apiClient';
import WardrobePreviewModal from './WardrobePreviewModal';
import { formatSpendSGD, formatTokens } from '../utils/formatters';

const CATEGORY_COLORS = {
  tops: '#0284c7',
  bottoms: '#c2410c',
  outerwear: '#6d28d9',
  footwear: '#047857',
  accessories: '#be185d',
  full_outfit: '#a16207',
};

export default function WardrobePanel({
  isOpen = false,
  onClose,
  assignments = [],
  onAddAssignment,
  onRemoveAssignment,
  onClearAssignments,
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
  const fileInputRef = useRef(null);

  // Load wardrobe library items on mount or when panel opens
  useEffect(() => {
    if (isOpen) {
      loadItems();
    }
  }, [isOpen]);

  // Auto-poll while any garments are pending or processing AI detail upscaling
  useEffect(() => {
    if (!isOpen) return;
    const hasPendingUpscale = items.some(
      (item) => item.upscale_status === 'pending' || item.upscale_status === 'processing'
    );
    if (!hasPendingUpscale) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetchWardrobeItems();
        if (res.items) {
          setItems(res.items);
        }
      } catch (err) {
        console.warn('Failed to poll wardrobe items status:', err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [isOpen, items]);

  const loadItems = async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const res = await fetchWardrobeItems();
      setItems(res.items || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load wardrobe library.');
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
      const res = await uploadWardrobeSheet(file, visionModel);
      if (res.items && res.items.length > 0) {
        setItems((prev) => [...res.items, ...prev]);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to segment wardrobe sheet.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteItem = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Remove this garment from your wardrobe library?')) return;
    try {
      await deleteWardrobeItem(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      if (previewItemId === id) {
        setPreviewItemId(null);
      }
      // Remove any active assignment using this item
      assignments.forEach((asgn) => {
        if (asgn.wardrobe_item_id === id) {
          onRemoveAssignment?.(asgn.pin_number);
        }
      });
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete garment.');
    }
  };

  const handleDeleteAll = async () => {
    if (items.length === 0) return;
    if (!window.confirm(`Delete all ${items.length} garments from your wardrobe library?`)) return;
    try {
      setIsLoading(true);
      await deleteAllWardrobeItems();
      setItems([]);
      setPreviewItemId(null);
      onClearAssignments?.();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete all garments.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDragStart = (e, item) => {
    e.dataTransfer.setData('application/json', JSON.stringify(item));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleQuickAdd = (item) => {
    // Accessible fallback: clicking the garment or pressing Enter adds it with center coordinates
    onAddAssignment?.(item, { x: 0.5, y: 0.5 });
  };

  const filteredItems = selectedCategory === 'all'
    ? items
    : items.filter((item) => (item.category || 'tops').toLowerCase() === selectedCategory);

  if (!isOpen) return null;

  return (
    <aside className="wardrobe-panel-container" aria-label="Wardrobe Library Panel">
      {/* Header */}
      <div className="wardrobe-panel-header">
        <div className="wardrobe-header-title-row">
          <div className="wardrobe-title-badge">
            <Shirt size={16} className="text-accent" />
            <span>Wardrobe Studio</span>
          </div>
          <div className="wardrobe-header-actions">
            <span className="wardrobe-count-badge">
              {items.length} item{items.length !== 1 ? 's' : ''}
            </span>
            {items.length > 0 && (
              <button
                type="button"
                className="btn-text-danger"
                onClick={handleDeleteAll}
                title="Delete all garments from wardrobe library"
                aria-label="Delete all garments"
              >
                <Trash2 size={12} />
                <span>Delete All</span>
              </button>
            )}
            <button
              type="button"
              className="btn-icon-subtle"
              onClick={onClose}
              title="Close wardrobe panel"
              aria-label="Close Wardrobe Studio"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        <p className="wardrobe-subtitle">
          Upload multi-garment lookbooks. Drag items onto the subject in the viewport to swap clothing.
        </p>
      </div>

      {/* Upload Zone */}
      <div className="wardrobe-upload-section">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileUpload}
          aria-label="Upload garment image or lookbook"
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
          aria-label="Click to upload garment lookbook image"
        >
          {isUploading ? (
            <div className="wardrobe-uploading-spinner-row" role="status" aria-live="polite">
              <div className="generating-spinner" />
              <div className="upload-text-group">
                <span className="upload-main-text">Analyzing & Segmenting Sheet...</span>
                <span className="upload-sub-text">Gemini vision is detecting garment bounding boxes</span>
              </div>
            </div>
          ) : (
            <div className="wardrobe-dropzone-inner">
              <div className="dropzone-icon-circle">
                <Upload size={16} />
              </div>
              <div className="upload-text-group">
                <span className="upload-main-text">Upload Garment Sheet / Lookbook</span>
                <span className="upload-sub-text">Auto-segments into individual items</span>
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
      <div className="wardrobe-category-bar" role="tablist" aria-label="Garment categories">
        {['all', 'outerwear', 'tops', 'bottoms', 'footwear', 'accessories'].map((cat) => (
          <button
            key={cat}
            type="button"
            className={`category-pill ${selectedCategory === cat ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
            role="tab"
            aria-selected={selectedCategory === cat}
          >
            {cat === 'all' ? 'All Items' : cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {/* Garments Grid */}
      <div className="wardrobe-items-scroll" tabIndex={0} role="region" aria-label="Garment Library Items">
        {isLoading ? (
          <div className="wardrobe-empty-state" role="status" aria-live="polite">
            <RefreshCw size={24} className="animate-spin text-muted" />
            <p>Loading wardrobe library...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="gallery-empty-state wardrobe-empty-state" role="status">
            <div className="empty-icon-capsule wardrobe-capsule">
              <Shirt size={22} className="empty-capsule-icon" />
            </div>
            <h4 className="empty-title">
              {items.length === 0
                ? 'No Garments in Studio Library'
                : `No ${selectedCategory.charAt(0).toUpperCase() + selectedCategory.slice(1)} Garments`}
            </h4>
            <p className="empty-desc">
              {items.length === 0
                ? 'Upload a lookbook or catalog image to segment and extract wearable outfits and pieces.'
                : `No garments found in this category. You have ${items.length} item${items.length === 1 ? '' : 's'} in other categories.`}
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
                  <span>Upload Lookbook Sheet</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-gallery-empty-action"
                  onClick={() => setSelectedCategory('all')}
                >
                  <span>Show All Garments ({items.length})</span>
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="wardrobe-cards-grid">
            {filteredItems.map((item) => {
              const activePinCount = assignments.filter((a) => a.wardrobe_item_id === item.id).length;
              const catColor = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.tops;
              const isUpscaled = item.is_upscaled || item.upscale_status === 'completed';
              const isUpscaling = item.upscale_status === 'pending' || item.upscale_status === 'processing';
              const displayImageUrl = isUpscaled && item.upscaled_image_url ? item.upscaled_image_url : item.image_url;

              return (
                <div
                  key={item.id}
                  className={`garment-card ${activePinCount > 0 ? 'is-assigned' : ''}`}
                  draggable={true}
                  onDragStart={(e) => handleDragStart(e, { ...item, display_image_url: displayImageUrl })}
                  onClick={() => handleQuickAdd({ ...item, display_image_url: displayImageUrl })}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleQuickAdd({ ...item, display_image_url: displayImageUrl });
                    }
                  }}
                  title="Drag onto viewport or click to pin garment"
                  aria-label={`${item.label}, Category: ${item.category || 'tops'}${isUpscaled ? ', HD Upscaled' : ''}`}
                >
                  <div className="garment-thumb-wrap">
                    <img
                      src={displayImageUrl}
                      alt={item.label}
                      className="garment-thumb-img"
                      loading="lazy"
                    />
                    <div className="garment-drag-overlay">
                      <GripHorizontal size={14} />
                      <span>Drag to Viewport</span>
                    </div>
                    {activePinCount > 0 && (
                      <div className="garment-active-pin-badge">
                        <span>Pinned ({activePinCount})</span>
                      </div>
                    )}
                    {isUpscaling && (
                      <div className="garment-upscaling-badge" title="AI detail enhancement & upscaling in progress">
                        <Sparkles size={10} className="animate-spin text-accent" />
                        <span>Enhancing...</span>
                      </div>
                    )}
                    {isUpscaled && !isUpscaling && (
                      <div className="garment-hd-badge" title="AI 4K high-definition detail upscaled with graphic invariance">
                        <span>HD Lock</span>
                      </div>
                    )}
                    {(Number(item.cost_sgd || 0) > 0 || Number(item.cost_usd || 0) > 0) && (
                      <div className="garment-cost-badge" title={`API Cost: ${formatSpendSGD(item.cost_sgd, item.cost_usd)} (${formatTokens(item.tokens || 0)} tokens)`}>
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
                          {item.category || 'tops'}
                        </span>
                        {item.extracted_details?.has_text_or_logo && item.extracted_details?.exact_text_content?.length > 0 && (
                          <span
                            className="garment-feature-tag tag-cyan"
                            title={`Exact Text: ${item.extracted_details.exact_text_content.join(', ')}`}
                          >
                            Text Lock
                          </span>
                        )}
                        {item.extracted_details?.has_graphic_or_print && (
                          <span
                            className="garment-feature-tag tag-purple"
                            title={`Graphic Print: ${item.extracted_details.graphic_description || 'Artwork detected'}`}
                          >
                            Graphic
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
                        title="Preview & inspect garment quality"
                        aria-label={`Preview quality of ${item.label}`}
                      >
                        <Eye size={12} />
                      </button>
                      <button
                        type="button"
                        className="garment-action-btn garment-delete-btn"
                        onClick={(e) => handleDeleteItem(e, item.id)}
                        title="Delete garment"
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

      {/* Queued Assignments & Composition Bar */}
      <div className="wardrobe-assignments-footer">
        <div className="assignments-header-row">
          <div className="assignments-title-group">
            <Layers size={14} className="text-accent" />
            <span className="assignments-title">Queued Swaps ({assignments.length})</span>
          </div>
          {assignments.length > 0 && (
            <button
              type="button"
              className="btn-text-subtle"
              onClick={onClearAssignments}
              disabled={isComposing}
              aria-label="Clear all pinned assignments"
            >
              Clear All
            </button>
          )}
        </div>

        {assignments.length === 0 ? (
          <div className="assignments-empty-hint">
            <HelpCircle size={13} className="text-muted" />
            <span>Drag a garment card above and drop it directly onto the model in the viewport.</span>
          </div>
        ) : (
          <div className="assignments-chips-list">
            {assignments.map((asgn) => (
              <div key={asgn.pin_number} className="assignment-chip">
                <span className="assignment-pin-num">#{asgn.pin_number}</span>
                <span className="assignment-item-label">{asgn.item_label || 'Garment'}</span>
                <button
                  type="button"
                  className="assignment-remove-btn"
                  onClick={() => onRemoveAssignment?.(asgn.pin_number)}
                  title="Remove this pin"
                  disabled={isComposing}
                  aria-label={`Remove pin #${asgn.pin_number}`}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Optional Custom Directive */}
        {assignments.length > 0 && (
          <div className="wardrobe-instruction-input-wrap">
            <input
              type="text"
              className="wardrobe-instruction-input"
              placeholder="Optional styling directive (e.g. 'Match sunlight reflections, untucked')..."
              value={customInstruction}
              onChange={(e) => setCustomInstruction(e.target.value)}
              disabled={isComposing}
              aria-label="Custom wardrobe styling directive"
            />
          </div>
        )}

        {/* Compose Button */}
        <button
          type="button"
          className="btn-primary compose-btn"
          disabled={assignments.length === 0 || isComposing || !activeGenerationId}
          onClick={() => onCompose?.(customInstruction)}
        >
          {isComposing ? (
            <>
              <div className="btn-spinner" />
              <span>Composing Multi-Garment Swap...</span>
            </>
          ) : (
            <>
              <Sparkles size={14} />
              <span>
                {assignments.length === 0
                  ? 'Drag Garments to Viewport'
                  : `Compose Swaps (${assignments.length} item${assignments.length !== 1 ? 's' : ''})`}
              </span>
            </>
          )}
        </button>
      </div>

      {/* Garment Quality Inspector & Preview Modal */}
      <WardrobePreviewModal
        isOpen={previewItemId !== null}
        onClose={() => setPreviewItemId(null)}
        items={filteredItems}
        initialItemId={previewItemId}
        onAddAssignment={onAddAssignment}
        onDeleteItem={handleDeleteItem}
        onUpdateItem={(updated) => {
          setItems((prev) =>
            prev.map((it) => (it.id === updated.id ? { ...it, ...updated } : it))
          );
        }}
      />
    </aside>
  );
}
