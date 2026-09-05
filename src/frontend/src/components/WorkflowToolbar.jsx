import React, { useState } from 'react';
import {
  Ratio,
  Square,
  RectangleHorizontal,
  RectangleVertical,
  Lock,
  Unlock,
  Dice5,
  Copy,
  Check,
  ChevronDown,
  Shirt,
  Box,
  Sparkles,
  Paintbrush,
} from 'lucide-react';
import {
  ASPECT_RATIO_OPTIONS,
  ASPECT_RATIO_MASTERS,
  parseAspectRatio,
} from '../constants/aspectRatios';

/**
 * Reusable Workflow Toolbar rendered across all pipeline stages.
 * Provides a synchronized Aspect Ratio dropdown, Adjust submode toggle (Refinement / Adjust),
 * Scene submode toggle (Wardrobe / Props), and Active Seed status badge.
 * 
 * @param {Object} props
 * @param {string} props.aspectRatio - Current active aspect ratio (e.g., '1:1', '4:5', '16:9')
 * @param {Function} props.onAspectRatioChange - Callback when aspect ratio is changed
 * @param {'refinement' | 'canvas_inpaint' | 'adjust'} [props.adjustSubMode='refinement'] - Current adjust studio sub-mode
 * @param {Function} [props.onAdjustSubModeChange] - Callback to toggle adjust submode
 * @param {boolean} [props.showAdjustSubMode=false] - Whether to display the Refinement / Canvas Inpaint toggle
 * @param {'wardrobe' | 'props'} [props.sceneSubMode='wardrobe'] - Current scene studio sub-mode
 * @param {Function} [props.onSceneSubModeChange] - Callback to toggle scene submode
 * @param {boolean} [props.showSceneSubMode=false] - Whether to display the Wardrobe / Props toggle
 * @param {number} [props.activeSeed] - Current active generation seed
 * @param {'locked' | 'random'} [props.seedMode='locked'] - Current seed mode
 * @param {Function} [props.onSeedModeChange] - Callback to toggle seed mode
 * @param {boolean} [props.disabled=false] - Whether controls should be disabled during generation
 * @param {string} [props.className=''] - Additional CSS classes
 */
export default function WorkflowToolbar({
  aspectRatio = '1:1',
  onAspectRatioChange,
  adjustSubMode = 'refinement',
  onAdjustSubModeChange,
  showAdjustSubMode = false,
  sceneSubMode = 'wardrobe',
  onSceneSubModeChange,
  showSceneSubMode = false,
  activeSeed,
  seedMode = 'locked',
  onSeedModeChange,
  disabled = false,
  className = '',
}) {
  const [copiedSeed, setCopiedSeed] = useState(false);

  const ratioInfo = parseAspectRatio(aspectRatio);
  const activeMasterRes = ASPECT_RATIO_MASTERS[aspectRatio] || { width: 3840, height: 3840 };
  const currentOption = ASPECT_RATIO_OPTIONS.find((opt) => opt.id === aspectRatio);

  const handleCopySeed = async (e) => {
    e.stopPropagation();
    if (activeSeed !== undefined && activeSeed !== null) {
      try {
        await navigator.clipboard.writeText(String(activeSeed));
        setCopiedSeed(true);
        setTimeout(() => setCopiedSeed(false), 2000);
      } catch (err) {
        console.error('Failed to copy seed', err);
      }
    }
  };

  const renderRatioIcon = (orientation, size = 15) => {
    if (orientation === 'square') {
      return <Square size={size} className="text-accent" />;
    }
    if (orientation === 'horizontal') {
      return <RectangleHorizontal size={size} className="text-accent" />;
    }
    return <RectangleVertical size={size} className="text-accent" />;
  };

  return (
    <div className={`workflow-toolbar ${className}`.trim()} role="toolbar" aria-label="Workflow Context & Canvas Controls">
      {/* Left: Aspect Ratio Control Group & Scene Studio Submode */}
      <div className="workflow-toolbar-left">
        <div className="workflow-toolbar-group workflow-toolbar-ratio-group">
          <div className="workflow-ratio-selector-wrap">
            <span className="workflow-toolbar-icon-box" title={`Orientation: ${ratioInfo.orientation}`}>
              {renderRatioIcon(ratioInfo.orientation, 15)}
            </span>
            <label htmlFor="workflow-aspect-ratio-select" className="workflow-toolbar-label">
              Aspect Ratio:
            </label>
            <div className="workflow-select-container">
              <select
                id="workflow-aspect-ratio-select"
                aria-label="Workflow Aspect Ratio Selection"
                className="workflow-ratio-select"
                value={aspectRatio}
                onChange={(e) => onAspectRatioChange?.(e.target.value)}
                disabled={disabled}
              >
                {ASPECT_RATIO_OPTIONS.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name} ({opt.width}×{opt.height})
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="workflow-select-chevron" />
            </div>
          </div>

          {/* Resolution Specs Tag */}
          <div className="workflow-res-tag" title={`Target 4K Master Canvas: ${activeMasterRes.width}×${activeMasterRes.height} px`}>
            <span className="workflow-res-pill">
              4K • {activeMasterRes.width}×{activeMasterRes.height}
            </span>
          </div>
        </div>

        {/* Immediately adjacent: Adjust Studio Mode Toggle [ ✨ Refinement | 🖌️ Adjust ] */}
        {showAdjustSubMode && (
          <div className="workflow-toolbar-group workflow-toolbar-adjust-submode">
            <div className="workflow-toolbar-divider" aria-hidden="true" />
            <span className="workflow-toolbar-label">Adjust Studio:</span>
            <div className="scene-submode-pill-toggle" role="group" aria-label="Adjust Studio Mode">
              <button
                type="button"
                className={`scene-submode-btn ${adjustSubMode === 'refinement' ? 'active' : ''}`}
                onClick={() => onAdjustSubModeChange?.('refinement')}
                disabled={disabled}
                aria-pressed={adjustSubMode === 'refinement'}
                title="Switch to Conversational Refinement"
              >
                <Sparkles size={14} className="scene-submode-icon" />
                <span>Refinement</span>
              </button>
              <button
                type="button"
                className={`scene-submode-btn ${adjustSubMode === 'adjust' || adjustSubMode === 'canvas_inpaint' ? 'active' : ''}`}
                onClick={() => onAdjustSubModeChange?.('canvas_inpaint')}
                disabled={disabled}
                aria-pressed={adjustSubMode === 'adjust' || adjustSubMode === 'canvas_inpaint'}
                title="Switch to Canvas Inpainting & Targeted Adjustments"
              >
                <Paintbrush size={14} className="scene-submode-icon" />
                <span>Canvas Inpaint</span>
              </button>
            </div>
          </div>
        )}

        {/* Immediately adjacent: Scene Studio Mode Toggle [ 👔 Wardrobe | 📦 Props ] */}
        {showSceneSubMode && (
          <div className="workflow-toolbar-group workflow-toolbar-scene-submode">
            <div className="workflow-toolbar-divider" aria-hidden="true" />
            <span className="workflow-toolbar-label">Scene Studio:</span>
            <div className="scene-submode-pill-toggle" role="group" aria-label="Scene Studio Mode">
              <button
                type="button"
                className={`scene-submode-btn ${sceneSubMode === 'wardrobe' ? 'active' : ''}`}
                onClick={() => onSceneSubModeChange?.('wardrobe')}
                disabled={disabled}
                aria-pressed={sceneSubMode === 'wardrobe'}
                title="Switch to Wardrobe & Garment Swapper"
              >
                <Shirt size={14} className="scene-submode-icon" />
                <span>Wardrobe</span>
              </button>
              <button
                type="button"
                className={`scene-submode-btn ${sceneSubMode === 'props' ? 'active' : ''}`}
                onClick={() => onSceneSubModeChange?.('props')}
                disabled={disabled}
                aria-pressed={sceneSubMode === 'props'}
                title="Switch to Props Studio & Object Placement"
              >
                <Box size={14} className="scene-submode-icon" />
                <span>Props</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Right: Active Seed Status Badge */}
      <div className="workflow-toolbar-right">
        {activeSeed !== undefined && activeSeed !== null && (
          <div className="workflow-toolbar-group workflow-toolbar-seed-group">
          <div
            className={`workflow-seed-badge ${seedMode === 'locked' ? 'seed-locked' : 'seed-random'}`}
            title={
              seedMode === 'locked'
                ? `Seed #${activeSeed} is locked for deterministic reproducibility. Click to copy.`
                : `Seed will randomize on each generation turn. Click to copy current seed #${activeSeed}.`
            }
          >
            <div className="workflow-seed-mode-icon">
              {seedMode === 'locked' ? <Lock size={12} className="text-warning" /> : <Dice5 size={12} className="text-purple" />}
            </div>
            <span className="workflow-seed-label">Seed:</span>
            <span className="workflow-seed-value">#{activeSeed}</span>

            {onSeedModeChange && (
              <button
                type="button"
                className="workflow-seed-toggle-btn"
                onClick={() => onSeedModeChange(seedMode === 'locked' ? 'random' : 'locked')}
                disabled={disabled}
                title={seedMode === 'locked' ? 'Switch to Randomize Seed' : 'Switch to Lock Seed'}
                aria-label={seedMode === 'locked' ? 'Switch to Randomize Seed' : 'Switch to Lock Seed'}
              >
                {seedMode === 'locked' ? 'Lock' : 'Rand'}
              </button>
            )}

            <button
              type="button"
              className="workflow-seed-copy-btn"
              onClick={handleCopySeed}
              title="Copy seed to clipboard"
              aria-label="Copy seed to clipboard"
            >
              {copiedSeed ? <Check size={11} className="text-success" /> : <Copy size={11} />}
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
