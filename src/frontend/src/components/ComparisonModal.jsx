import React, { useState, useMemo } from 'react';
import {
  X,
  Split,
  Layers,
  ArrowLeftRight,
  Hash,
  Terminal,
  Copy,
  Check,
  FileText,
} from 'lucide-react';

export default function ComparisonModal({
  isOpen = false,
  onClose,
  versionA = null,
  versionB = null,
}) {
  const [sliderPos, setSliderPos] = useState(50);
  const [copiedA, setCopiedA] = useState(false);
  const [copiedB, setCopiedB] = useState(false);

  if (!isOpen || !versionA || !versionB) {
    return null;
  }

  const urlA = versionA.master_image_url || versionA.image_url;
  const urlB = versionB.master_image_url || versionB.image_url;

  const promptA = versionA.compiled_prompt || versionA.prompt || '';
  const promptB = versionB.compiled_prompt || versionB.prompt || '';

  const schemaA = versionA.schema_json || versionA.schema || {};
  const schemaB = versionB.schema_json || versionB.schema || {};

  const handleCopyA = async () => {
    if (!promptA) return;
    try {
      await navigator.clipboard.writeText(promptA);
      setCopiedA(true);
      setTimeout(() => setCopiedA(false), 2000);
    } catch (err) {
      console.error('Failed to copy prompt A', err);
    }
  };

  const handleCopyB = async () => {
    if (!promptB) return;
    try {
      await navigator.clipboard.writeText(promptB);
      setCopiedB(true);
      setTimeout(() => setCopiedB(false), 2000);
    } catch (err) {
      console.error('Failed to copy prompt B', err);
    }
  };

  // Compute key diffs between schemas
  const diffEntries = useMemo(() => {
    const diffs = [];
    const allKeys = Array.from(new Set([...Object.keys(schemaA), ...Object.keys(schemaB)]));

    allKeys.forEach((key) => {
      const valA = schemaA[key];
      const valB = schemaB[key];
      const strA = JSON.stringify(valA);
      const strB = JSON.stringify(valB);

      if (strA !== strB) {
        diffs.push({
          key,
          valA: valA !== undefined ? JSON.stringify(valA, null, 1) : 'None',
          valB: valB !== undefined ? JSON.stringify(valB, null, 1) : 'None',
        });
      }
    });
    return diffs;
  }, [schemaA, schemaB]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="comparison-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="comparison-modal-header">
          <div className="comparison-title-group">
            <Split size={18} className="text-accent" />
            <span className="comparison-title">Side-by-Side Split-Slider Diff</span>
          </div>

          <div className="comparison-version-labels">
            <span className="version-pill version-a">
              Version A: #{versionA.seed} ({versionA.is_baseline ? 'Baseline' : 'Iteration'})
            </span>
            <ArrowLeftRight size={14} className="text-muted" />
            <span className="version-pill version-b">
              Version B: #{versionB.seed} ({versionB.is_baseline ? 'Baseline' : 'Iteration'})
            </span>
          </div>

          <button type="button" className="modal-close-btn" onClick={onClose} title="Close">
            <X size={18} />
          </button>
        </div>

        {/* Modal Body: Split Slider + Diff Table + Prompts Diff */}
        <div className="comparison-modal-body">
          {/* Interactive Split Viewport */}
          <div className="split-slider-viewport">
            {/* Version A Background (Full) */}
            <img src={urlA} alt="Version A" className="split-image-layer layer-a" />

            {/* Version B Clipped Layer */}
            <div
              className="split-image-layer layer-b"
              style={{
                clipPath: `inset(0 0 0 ${sliderPos}%)`,
              }}
            >
              <img src={urlB} alt="Version B" className="split-image-inner" />
            </div>

            {/* Divider Line */}
            <div className="split-divider-line" style={{ left: `${sliderPos}%` }}>
              <div className="split-handle">
                <ArrowLeftRight size={12} />
              </div>
            </div>

            {/* Range Input Overlay */}
            <input
              type="range"
              min="0"
              max="100"
              value={sliderPos}
              onChange={(e) => setSliderPos(Number(e.target.value))}
              className="split-range-input"
            />
          </div>

          {/* Prompt Comparison Section */}
          <div className="comparison-prompts-grid">
            <div className="comparison-prompt-card">
              <div className="comparison-prompt-header">
                <div className="flex items-center gap-2">
                  <Terminal size={13} className="text-accent" />
                  <span className="font-semibold text-xs text-secondary">Version A Prompt (Seed #{versionA.seed})</span>
                </div>
                <button
                  type="button"
                  className="btn-prompt-action"
                  onClick={handleCopyA}
                  title="Copy Version A Prompt"
                >
                  {copiedA ? (
                    <>
                      <Check size={11} className="text-success" />
                      <span className="text-success text-xs">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy size={11} />
                      <span className="text-xs">Copy</span>
                    </>
                  )}
                </button>
              </div>
              <div className="comparison-prompt-box">
                {promptA || 'No compiled prompt recorded'}
              </div>
            </div>

            <div className="comparison-prompt-card">
              <div className="comparison-prompt-header">
                <div className="flex items-center gap-2">
                  <Terminal size={13} className="text-accent" />
                  <span className="font-semibold text-xs text-secondary">Version B Prompt (Seed #{versionB.seed})</span>
                </div>
                <button
                  type="button"
                  className="btn-prompt-action"
                  onClick={handleCopyB}
                  title="Copy Version B Prompt"
                >
                  {copiedB ? (
                    <>
                      <Check size={11} className="text-success" />
                      <span className="text-success text-xs">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy size={11} />
                      <span className="text-xs">Copy</span>
                    </>
                  )}
                </button>
              </div>
              <div className="comparison-prompt-box">
                {promptB || 'No compiled prompt recorded'}
              </div>
            </div>
          </div>

          {/* Schema Differences Table */}
          <div className="comparison-diff-panel">
            <div className="diff-panel-header">
              <Layers size={14} className="text-accent" />
              <span>JSON Parameter Differences ({diffEntries.length} modified sections)</span>
            </div>

            <div className="diff-table-container">
              {diffEntries.length === 0 ? (
                <div className="diff-empty">Identical schema parameters between versions.</div>
              ) : (
                <table className="diff-table">
                  <thead>
                    <tr>
                      <th>Section Key</th>
                      <th>Version A Value</th>
                      <th>Version B Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diffEntries.map((diff) => (
                      <tr key={diff.key}>
                        <td className="diff-key-cell">{diff.key}</td>
                        <td className="diff-val-cell">{diff.valA}</td>
                        <td className="diff-val-cell diff-val-highlight">{diff.valB}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
