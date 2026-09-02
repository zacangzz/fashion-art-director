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
} from 'lucide-react';
import {
  ASPECT_RATIO_OPTIONS,
  ASPECT_RATIO_MASTERS,
  parseAspectRatio,
} from '../constants/aspectRatios';

/**
 * Reusable Workflow Toolbar rendered across all pipeline stages.
 * Provides a synchronized Aspect Ratio dropdown and Active Seed status badge.
 * 
 * @param {Object} props
 * @param {string} props.aspectRatio - Current active aspect ratio (e.g., '1:1', '4:5', '16:9')
 * @param {Function} props.onAspectRatioChange - Callback when aspect ratio is changed
 * @param {number} [props.activeSeed] - Current active generation seed
 * @param {'locked' | 'random'} [props.seedMode='locked'] - Current seed mode
 * @param {Function} [props.onSeedModeChange] - Callback to toggle seed mode
 * @param {boolean} [props.disabled=false] - Whether controls should be disabled during generation
 * @param {string} [props.className=''] - Additional CSS classes
 */
export default function WorkflowToolbar({
  aspectRatio = '1:1',
  onAspectRatioChange,
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
      {/* Left: Aspect Ratio Control Group */}
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

      {/* Right: Active Seed Status Badge */}
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
  );
}
