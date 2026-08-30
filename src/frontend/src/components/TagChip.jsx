import React, { useState } from 'react';
import { Lock, Unlock, X, AlertTriangle } from 'lucide-react';

const CATEGORY_COLORS = {
  subject_details: '#06b6d4',
  objects_props: '#f97316',
  wardrobe_hair: '#ec4899',
  environment: '#84cc16',
  layout_framing: '#10b981',
  lighting: '#f59e0b',
  color_profile: '#e11d48',
  camera_optics: '#a855f7',
  mood_era: '#3b82f6',
  custom: '#64748b',
};

export default function TagChip({ chip, onUpdate, onDelete, isConflicted = false, conflictReason = '' }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(chip.label);

  const accentColor = CATEGORY_COLORS[chip.category] || CATEGORY_COLORS.custom;

  const handleToggleLock = (e) => {
    e.stopPropagation();
    onUpdate(chip.id, { locked: !chip.locked });
  };

  const handleStartEdit = (e) => {
    e.stopPropagation();
    setIsEditing(true);
    setEditValue(chip.label);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') {
      submitEdit();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setEditValue(chip.label);
    }
  };

  const submitEdit = () => {
    setIsEditing(false);
    const trimmed = editValue.trim();
    if (trimmed) {
      onUpdate(chip.id, { label: trimmed, enabled: true });
    }
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    onDelete(chip.id);
  };

  return (
    <div
      className={`tag-chip enabled ${chip.locked ? 'locked' : ''} ${isConflicted ? 'tag-chip-conflicted' : ''}`}
      style={{
        '--chip-color': isConflicted ? '#f59e0b' : accentColor,
        '--chip-bg': isConflicted ? 'rgba(245, 158, 11, 0.15)' : `${accentColor}1A`,
        '--chip-border': isConflicted ? '#f59e0b' : `${accentColor}99`,
        cursor: 'default',
      }}
    >
      {/* Conflict Warning Indicator */}
      {isConflicted && (
        <span
          className="tag-conflict-icon"
          title={conflictReason || 'This tag is part of a detected prompt conflict'}
          style={{ color: '#f59e0b', display: 'flex', alignItems: 'center' }}
        >
          <AlertTriangle size={12} />
        </span>
      )}

      {/* Lock Button */}
      <button
        type="button"
        aria-label={chip.locked ? 'Unlock tag' : 'Lock tag'}
        className={`tag-chip-btn lock-btn ${chip.locked ? 'locked' : ''}`}
        onClick={handleToggleLock}
        title={chip.locked ? 'Locked: preserved during re-analysis' : 'Click to lock tag'}
      >
        {chip.locked ? <Lock size={12} /> : <Unlock size={12} />}
      </button>

      {/* Category Indicator Dot */}
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isConflicted ? '#f59e0b' : accentColor,
          boxShadow: `0 0 6px ${isConflicted ? '#f59e0b' : accentColor}`,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />

      {/* Label / Inline Edit Input */}
      {isEditing ? (
        <input
          type="text"
          className="tag-chip-edit-input"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={submitEdit}
          onKeyDown={handleEditKeyDown}
          autoFocus
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span
          className="tag-chip-label"
          onClick={handleStartEdit}
          title="Click to edit tag text"
        >
          {chip.label}
        </span>
      )}

      {/* Delete Tag Button */}
      <button
        type="button"
        aria-label="Delete tag"
        className="tag-chip-btn delete-btn"
        onClick={handleDeleteClick}
        title="Remove tag"
      >
        <X size={12} />
      </button>
    </div>
  );
}
