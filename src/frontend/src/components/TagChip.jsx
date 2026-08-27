import React, { useState } from 'react';
import { Lock, Unlock, X, Edit2 } from 'lucide-react';

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

export default function TagChip({ chip, onUpdate, onDelete }) {
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
      className={`tag-chip enabled ${chip.locked ? 'locked' : ''}`}
      style={{
        '--chip-color': accentColor,
        '--chip-bg': `${accentColor}1F`,
        cursor: 'default',
      }}
    >
      {/* Lock Button */}
      <button
        type="button"
        aria-label={chip.locked ? 'Unlock tag' : 'Lock tag'}
        className="btn-icon"
        style={{
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: 0,
          display: 'flex',
          opacity: chip.locked ? 1 : 0.4,
        }}
        onClick={handleToggleLock}
        title={chip.locked ? 'Locked: preserved during re-analysis' : 'Click to lock tag'}
      >
        {chip.locked ? <Lock size={12} /> : <Unlock size={12} />}
      </button>

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
          onClick={handleStartEdit}
          title="Click to edit tag text"
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
        >
          {chip.label}
        </span>
      )}

      {/* Delete Tag Button */}
      <button
        type="button"
        aria-label="Delete tag"
        style={{
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: 0,
          display: 'flex',
          opacity: 0.6,
        }}
        onClick={handleDeleteClick}
        title="Remove tag"
      >
        <X size={12} />
      </button>
    </div>
  );
}
