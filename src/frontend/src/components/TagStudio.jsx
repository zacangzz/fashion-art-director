import React, { useState, useMemo } from 'react';
import {
  Layers,
  Sparkles,
  Lock,
  Unlock,
  Plus,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  Sliders,
  Image as ImageIcon,
  Diff,
} from 'lucide-react';
import TagChip from './TagChip';
import { CATEGORIES } from '../utils/defaultTags';
import {
  compileModularPrompt,
  compileDeltaPrompt,
  getModifiedCategories,
} from '../utils/promptCompiler';

export default function TagStudio({
  tagState = {},
  onUpdateTagState,
  lockedCategories = [],
  onToggleCategoryLock,
  baselineTagSnapshot = null,
  useImageReference = true,
  onToggleImageReference,
  onResetToBaseline,
}) {
  const [collapsedCategories, setCollapsedCategories] = useState({});
  const [newTagInputs, setNewTagInputs] = useState({});
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [previewTab, setPreviewTab] = useState('auto'); // 'auto', 'delta', 'full'

  const categories = tagState.categories || {};

  // Detect differences against baseline snapshot
  const diffInfo = useMemo(() => {
    return getModifiedCategories(
      categories,
      baselineTagSnapshot?.categories
    );
  }, [categories, baselineTagSnapshot]);

  // Live compiled delta prompt
  const deltaPrompt = useMemo(() => {
    return compileDeltaPrompt({
      categories,
      baselineCategories: baselineTagSnapshot?.categories || null,
      lockedCategories,
    });
  }, [categories, baselineTagSnapshot, lockedCategories]);

  // Live compiled full modular prompt
  const fullModularPrompt = useMemo(() => {
    return compileModularPrompt(categories);
  }, [categories]);

  // Active compiled prompt based on mode and settings
  const compiledPrompt = useMemo(() => {
    if (previewTab === 'full') return fullModularPrompt;
    if (previewTab === 'delta') return deltaPrompt;
    // 'auto' mode
    if (useImageReference && baselineTagSnapshot?.categories) {
      return deltaPrompt;
    }
    return fullModularPrompt;
  }, [previewTab, useImageReference, baselineTagSnapshot, deltaPrompt, fullModularPrompt]);

  const isDeltaActive = useImageReference && Boolean(baselineTagSnapshot?.categories);

  const toggleCollapse = (catKey) => {
    setCollapsedCategories((prev) => ({ ...prev, [catKey]: !prev[catKey] }));
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

  const handleAddTag = (catKey) => {
    const text = (newTagInputs[catKey] || '').trim();
    if (!text) return;

    const currentList = categories[catKey] || [];
    const newChip = {
      id: `tag_${catKey}_${Date.now()}`,
      category: catKey,
      label: text,
      enabled: true,
      locked: lockedCategories.includes(catKey),
      weight: 1.0,
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
  };

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(compiledPrompt);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2000);
  };

  return (
    <div
      className="panel"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        overflow: 'hidden',
        background: 'var(--surface-bg)',
      }}
    >
      {/* Studio Header */}
      <div className="section-title" style={{ flexShrink: 0, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} color="var(--accent-primary)" />
          <span style={{ fontWeight: 700 }}>Macro Studio (Visual Levers & Prompt Compiler)</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Preserve Reference Toggle */}
          {onToggleImageReference && (
            <button
              type="button"
              className="btn"
              title={
                useImageReference
                  ? 'Image reference conditioning active: preserves character identity & background'
                  : 'Image reference conditioning off: generates variations from scratch'
              }
              style={{
                fontSize: '0.72rem',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                background: useImageReference ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                color: useImageReference ? '#10b981' : 'var(--text-muted)',
                border: `1px solid ${useImageReference ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.08)'}`,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              onClick={onToggleImageReference}
            >
              <ImageIcon size={12} />
              {useImageReference ? 'Preserve Reference' : 'Free Generation'}
            </button>
          )}

          {/* Reset to Baseline Button */}
          {onResetToBaseline && diffInfo.hasChanges && (
            <button
              type="button"
              className="btn"
              title="Revert all tag modifications back to the original baseline state"
              style={{
                fontSize: '0.72rem',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              onClick={onResetToBaseline}
            >
              <RotateCcw size={12} />
              Reset to Base
            </button>
          )}

          <span
            style={{
              fontSize: '0.72rem',
              color: 'var(--text-muted)',
              background: 'rgba(255,255,255,0.06)',
              padding: '3px 8px',
              borderRadius: '12px',
            }}
          >
            {CATEGORIES.length} Categories
          </span>
        </div>
      </div>


      {/* 9 Categories Accordion List */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          paddingRight: '4px',
        }}
      >
        {CATEGORIES.map((cat) => {
          const catChips = categories[cat.key] || [];
          const isCollapsed = !!collapsedCategories[cat.key];
          const isLocked = lockedCategories.includes(cat.key);
          const isModified = Boolean(diffInfo.categories[cat.key]);
          const activeCount = catChips.filter((c) => c.enabled !== false).length;

          return (
            <div
              key={cat.key}
              className="category-card"
              style={{
                '--category-accent': cat.color,
                border: `1px solid ${isModified ? '#f59e0b' : isLocked ? cat.color : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(15, 23, 42, 0.4)',
                overflow: 'hidden',
                transition: 'border-color 0.2s ease',
              }}
            >
              {/* Category Header */}
              <div
                className="category-header"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  cursor: 'pointer',
                  background: isLocked
                    ? `${cat.color}14`
                    : isModified
                    ? 'rgba(245, 158, 11, 0.08)'
                    : 'rgba(255, 255, 255, 0.02)',
                }}
                onClick={() => toggleCollapse(cat.key)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: cat.color,
                      boxShadow: `0 0 8px ${cat.color}80`,
                    }}
                  />
                  <span style={{ fontWeight: 600, fontSize: '0.86rem', color: 'var(--text-primary)' }}>
                    {cat.label}
                  </span>

                  <span
                    style={{
                      fontSize: '0.7rem',
                      background: 'rgba(255, 255, 255, 0.08)',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      color: activeCount > 0 ? cat.color : 'var(--text-muted)',
                      fontWeight: 600,
                    }}
                  >
                    {activeCount} active
                  </span>

                  {isModified && (
                    <span
                      style={{
                        fontSize: '0.66rem',
                        background: 'rgba(245, 158, 11, 0.2)',
                        color: '#f59e0b',
                        padding: '1px 6px',
                        borderRadius: '6px',
                        fontWeight: 700,
                      }}
                    >
                      Modified
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {onToggleCategoryLock && (
                    <button
                      type="button"
                      aria-label={isLocked ? `Unlock ${cat.label}` : `Lock ${cat.label}`}
                      style={{
                        background: isLocked ? `${cat.color}33` : 'rgba(255,255,255,0.05)',
                        border: 'none',
                        color: isLocked ? cat.color : 'var(--text-muted)',
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.72rem',
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleCategoryLock(cat.key);
                      }}
                    >
                      {isLocked ? <Lock size={12} /> : <Unlock size={12} />}
                      {isLocked ? 'Locked' : 'Lock'}
                    </button>
                  )}
                  {isCollapsed ? <ChevronRight size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
                </div>
              </div>

              {/* Category Content */}
              {!isCollapsed && (
                <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                    {catChips.map((chip) => (
                      <TagChip
                        key={chip.id}
                        chip={{ ...chip, category: cat.key }}
                        onUpdate={(id, updates) => handleUpdateChip(cat.key, id, updates)}
                        onDelete={(id) => handleDeleteChip(cat.key, id)}
                      />
                    ))}

                    {catChips.length === 0 && (
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        No tags active. Add a custom tag below.
                      </span>
                    )}
                  </div>

                  {/* Add Tag Input */}
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <input
                      type="text"
                      placeholder={`+ Add tag to ${cat.label}...`}
                      value={newTagInputs[cat.key] || ''}
                      onChange={(e) => setNewTagInputs({ ...newTagInputs, [cat.key]: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(cat.key);
                        }
                      }}
                      style={{
                        flex: 1,
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--text-primary)',
                        padding: '5px 10px',
                        fontSize: '0.78rem',
                      }}
                    />
                    <button
                      type="button"
                      className="btn"
                      style={{
                        padding: '4px 10px',
                        fontSize: '0.75rem',
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: 'var(--text-primary)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                      onClick={() => handleAddTag(cat.key)}
                    >
                      <Plus size={12} />
                      Add
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Live Compiled Prompt Preview */}
      <div
        style={{
          flexShrink: 0,
          background: 'rgba(0, 0, 0, 0.35)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          padding: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Live Compiled Prompt
            </span>

            {/* Mode Indicator / Switcher */}
            <div style={{ display: 'flex', gap: '4px', background: 'rgba(0,0,0,0.3)', padding: '2px', borderRadius: '6px' }}>
              <button
                type="button"
                style={{
                  fontSize: '0.66rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  border: 'none',
                  background: isDeltaActive ? 'rgba(16, 185, 129, 0.25)' : 'transparent',
                  color: isDeltaActive ? '#10b981' : 'var(--text-muted)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '3px',
                }}
                onClick={() => setPreviewTab('delta')}
              >
                <Diff size={10} />
                Delta Mode
              </button>

              <button
                type="button"
                style={{
                  fontSize: '0.66rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  border: 'none',
                  background: !isDeltaActive ? 'rgba(6, 182, 212, 0.25)' : 'transparent',
                  color: !isDeltaActive ? '#06b6d4' : 'var(--text-muted)',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
                onClick={() => setPreviewTab('full')}
              >
                Full Scene
              </button>
            </div>
          </div>

          <button
            type="button"
            className="btn"
            style={{
              padding: '3px 8px',
              fontSize: '0.72rem',
              background: copiedPrompt ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.06)',
              color: copiedPrompt ? '#10b981' : 'var(--text-secondary)',
              borderRadius: 'var(--radius-sm)',
            }}
            onClick={handleCopyPrompt}
          >
            {copiedPrompt ? <Check size={12} /> : <Copy size={12} />}
            {copiedPrompt ? 'Copied' : 'Copy Prompt'}
          </button>
        </div>

        <div
          style={{
            background: 'rgba(0, 0, 0, 0.4)',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 10px',
            fontSize: '0.78rem',
            lineHeight: 1.45,
            color: 'var(--text-primary)',
            maxHeight: '75px',
            overflowY: 'auto',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            fontFamily: 'monospace',
          }}
        >
          {compiledPrompt}
        </div>
      </div>
    </div>
  );
}

