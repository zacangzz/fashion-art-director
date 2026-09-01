import React, { useRef } from 'react';
import {
  Image as ImageIcon,
  Upload,
  Trash2,
  Check,
  Sparkles,
  Layers,
  Clock,
  Plus,
} from 'lucide-react';
import Modal from './ui/Modal';
import Button from './ui/Button';
import Badge from './ui/Badge';
import Card from './ui/Card';

/**
 * Reusable Background Library Modal for selecting or uploading background reference images.
 * Composes Modal, Button, Badge, and Card primitives according to AGENTS.md guidelines.
 */
export default function BackgroundLibraryModal({
  isOpen,
  onClose,
  library = [],
  activeBackground = null,
  onSelectBackground,
  onUploadBackground,
  onDeleteBackground,
  isUploading = false,
  isLoading = false,
}) {
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await onUploadBackground(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleTriggerUpload = () => {
    fileInputRef.current?.click();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Reference Background Library"
      subtitle="Select or upload reference environments for perspective and lighting harmonization."
      icon={<Layers size={18} className="text-emerald-400" />}
      size="lg"
      className="bg-library-modal"
    >
      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        style={{ display: 'none' }}
        onChange={handleFileChange}
        disabled={isUploading}
      />

      {/* Top Action Bar */}
      <div className="bg-library-top-bar">
        <div className="bg-library-stats">
          <span className="text-xs text-muted">
            {library.length} stored reference{library.length !== 1 ? 's' : ''}
          </span>
        </div>

        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={14} />}
          onClick={handleTriggerUpload}
          loading={isUploading}
          disabled={isUploading}
        >
          Upload Background
        </Button>
      </div>

      {/* Main Grid View */}
      <div className="bg-library-grid-container" tabIndex={0} role="region" aria-label="Stored Backgrounds Grid">
        {library.length === 0 && !isLoading ? (
          <div className="bg-library-empty-state" onClick={handleTriggerUpload}>
            <div className="bg-empty-icon-wrap">
              <Upload size={28} className="text-emerald-400" />
            </div>
            <h4 className="bg-empty-title">No Background References Yet</h4>
            <p className="bg-empty-desc">
              Upload an architectural photo, street setting, or studio backdrop to re-use across all your iterations.
            </p>
            <Button
              variant="outline"
              size="sm"
              icon={<Upload size={14} />}
              loading={isUploading}
              onClick={(e) => {
                e.stopPropagation();
                handleTriggerUpload();
              }}
            >
              Upload First Background
            </Button>
          </div>
        ) : (
          <div className="bg-library-grid">
            {library.map((item) => {
              const isSelected = activeBackground?.id === item.id;
              return (
                <div
                  key={item.id}
                  className={`bg-library-card ${isSelected ? 'is-active-selected' : ''}`}
                  onClick={() => onSelectBackground(item)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectBackground(item);
                    }
                  }}
                  aria-pressed={isSelected}
                >
                  <div className="bg-card-image-wrap">
                    <img
                      src={item.thumbnail_url || item.image_url}
                      alt={item.original_filename || 'Background reference'}
                      className="bg-card-img"
                      loading="lazy"
                    />

                    {isSelected && (
                      <div className="bg-selected-overlay">
                        <Badge variant="success" size="xs" icon={<Check size={11} />}>
                          Active
                        </Badge>
                      </div>
                    )}

                    <div className="bg-card-actions-overlay">
                      <button
                        type="button"
                        className="bg-card-delete-btn"
                        title="Delete background reference"
                        aria-label={`Delete ${item.original_filename || 'background'}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteBackground(item.id);
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  <div className="bg-card-footer">
                    <span className="bg-card-filename" title={item.original_filename || item.id}>
                      {item.original_filename || item.id}
                    </span>
                    {item.aspect_ratio && (
                      <span className="bg-card-ratio-badge">{item.aspect_ratio}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
