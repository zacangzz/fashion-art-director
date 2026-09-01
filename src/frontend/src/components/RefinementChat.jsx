import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Sparkles,
  Send,
  Lock,
  Unlock,
  Shuffle,
  Clock,
  CheckCircle2,
  Image as ImageIcon,
  Shirt,
  Layers,
  Upload,
  X,
  Sliders,
  ChevronDown,
  ChevronUp,
  Camera,
  SunMedium,
  Compass,
} from 'lucide-react';
import Button from './ui/Button';
import Badge from './ui/Badge';
import Card from './ui/Card';
import BackgroundLibraryModal from './BackgroundLibraryModal';
import CameraSpatialStagerModal from './CameraSpatialStagerModal';
import { useBackgroundReference } from '../hooks/useBackgroundReference';

export default function RefinementChat({
  conversationMessages = [],
  onSendRefinement,
  isGenerating = false,
  activeSeed = 4289102,
  seedMode = 'locked',
  onSeedModeChange,
  onSeedChange,
  activeGenerationId = null,
  onSelectMessage,
  onToggleWardrobe,
  isWardrobeOpen = false,
  assignmentCount = 0,
}) {
  const [promptInput, setPromptInput] = useState('');
  const [showTuningTray, setShowTuningTray] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const bgUploadInputRef = useRef(null);

  // Background Reference Domain Hook
  const bg = useBackgroundReference();

  useEffect(() => {
    bg.loadLibrary();
  }, [bg.loadLibrary]);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversationMessages, isGenerating]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!promptInput.trim() || isGenerating) return;

    const bgOptions = bg.activeBackground
      ? {
          background_reference_id: bg.activeBackground.id,
          background_reference_url: bg.activeBackground.image_url,
          perspective_mode: bg.perspectiveMode,
          depth_of_field: bg.depthOfField,
          lighting_mode: bg.lightingMode,
          spatial_staging: bg.spatialStaging,
        }
      : {};

    onSendRefinement(promptInput.trim(), bgOptions);
    setPromptInput('');
  };


  const handleKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleRandomizeSeed = () => {
    const newSeed = Math.floor(Math.random() * 9000000) + 1000000;
    onSeedChange?.(newSeed);
  };

  const handleDirectBgUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await bg.handleUploadBackground(file);
    if (bgUploadInputRef.current) {
      bgUploadInputRef.current.value = '';
    }
  };

  return (
    <div className="refinement-chat-container" role="region" aria-label="Iterative Refinement Chat">
      {/* Hidden background quick upload input */}
      <input
        ref={bgUploadInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        style={{ display: 'none' }}
        onChange={handleDirectBgUpload}
      />

      {/* Header */}
      <div className="refinement-chat-header">
        <div className="refinement-header-title-row">
          <div className="refinement-title-badge">
            <MessageSquare size={16} />
            <span>Refinement Thread</span>
          </div>
          <span className="refinement-turn-count">
            {conversationMessages.length} iteration{conversationMessages.length !== 1 ? 's' : ''}
          </span>
        </div>
        <p className="refinement-header-subtitle">
          Direct changes naturally in plain English, swap wardrobe outfits, or attach background references with perspective harmonization.
        </p>

        {/* Seed & Control Bar */}
        <div className="refinement-controls-bar">
          <div className="refinement-control-group">
            <span className="control-label">Seed:</span>
            <button
              type="button"
              className={`seed-mode-toggle ${seedMode === 'locked' ? 'active' : ''}`}
              onClick={() => onSeedModeChange?.(seedMode === 'locked' ? 'random' : 'locked')}
              title={seedMode === 'locked' ? 'Seed is locked to preserve identity' : 'Seed is randomized for each iteration'}
              aria-label={seedMode === 'locked' ? 'Seed mode locked' : 'Seed mode random'}
            >
              {seedMode === 'locked' ? <Lock size={12} /> : <Unlock size={12} />}
              <span>{seedMode === 'locked' ? 'Locked' : 'Random'}</span>
            </button>
            <span className="seed-badge">#{activeSeed}</span>
            <button
              type="button"
              className="btn-icon-subtle"
              onClick={handleRandomizeSeed}
              title="Generate new random seed"
              aria-label="Randomize Seed"
            >
              <Shuffle size={13} />
            </button>
          </div>

          <div className="refinement-control-group">
            {/* Background Reference Studio Toggle */}
            <button
              type="button"
              className={`bg-toggle-btn ${bg.activeBackground ? 'active' : ''}`}
              onClick={() => bg.setIsLibraryOpen(true)}
              title="Attach a reference background environment with perspective harmonization"
              aria-label="Reference Background Library"
            >
              <Layers size={13} />
              <span>Background</span>
              {bg.activeBackground && <span className="bg-active-dot" />}
            </button>

            <button
              type="button"
              className="btn-icon-subtle"
              onClick={() => bgUploadInputRef.current?.click()}
              title="Upload reference background image"
              aria-label="Upload reference background"
            >
              <Upload size={13} />
            </button>

            {/* Wardrobe Studio Toggle */}
            <button
              type="button"
              className={`wardrobe-toggle-btn ${isWardrobeOpen ? 'active' : ''}`}
              onClick={onToggleWardrobe}
              title="Open Wardrobe Studio to swap clothes with multi-image references"
              aria-pressed={isWardrobeOpen}
              aria-label="Toggle Wardrobe Studio Panel"
            >
              <Shirt size={13} />
              <span>Wardrobe</span>
              {assignmentCount > 0 && <span className="wardrobe-pin-badge">{assignmentCount}</span>}
            </button>
          </div>
        </div>

        {/* Sticky Active Anchor Banner */}
        {conversationMessages.length > 0 && (() => {
          const activeMsg = conversationMessages.find((m) => m.generation_id === activeGenerationId) ||
            conversationMessages[conversationMessages.length - 1];
          const isBase = activeMsg.role === 'baseline';
          return (
            <div
              className="refinement-active-anchor-banner"
              title="This image is the active reference parent. The next refinement instruction will directly condition on this output."
              role="status"
              aria-live="polite"
            >
              <div className="anchor-banner-thumb-wrap">
                {activeMsg.image_url ? (
                  <img src={activeMsg.image_url} alt="Active Refinement Anchor" className="anchor-banner-thumb" />
                ) : (
                  <ImageIcon size={14} className="text-muted" />
                )}
                <span className="anchor-pulse-dot" />
              </div>
              <div className="anchor-banner-info">
                <div className="anchor-banner-title-row">
                  <span className="anchor-title-label">
                    {isBase
                      ? 'Anchor Baseline'
                      : activeMsg.is_inpaint
                      ? 'Active Inpaint Anchor'
                      : activeMsg.is_wardrobe
                      ? 'Active Wardrobe Anchor'
                      : activeMsg.background_reference_id
                      ? 'Active Background Harmonization'
                      : 'Active Refinement Anchor'}
                  </span>
                  <span className="anchor-seed-pill">Seed #{activeMsg.seed || activeSeed}</span>
                </div>
                <span className="anchor-subtext">Next prompt will refine from this image</span>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Message Timeline */}
      <div className="refinement-messages-list" tabIndex={0} role="feed" aria-label="Refinement History Feed">
        {conversationMessages.length === 0 ? (
          <div className="refinement-empty-state">
            <Sparkles size={32} className="text-muted" />
            <p className="empty-title">Ready for Refinements</p>
            <p className="empty-desc">
              Type instructions below like <q>Change the jacket to brown leather</q> or attach a background reference to re-project the scene environment.
            </p>
          </div>
        ) : (
          conversationMessages.map((msg, index) => {
            const isBaseline = msg.role === 'baseline' || index === 0;
            const isSelected = activeGenerationId ? activeGenerationId === msg.generation_id : index === conversationMessages.length - 1;
            const hasBgRef = Boolean(msg.background_reference_id || msg.background_reference_url);

            return (
              <div
                key={msg.generation_id || index}
                className={`refinement-message-card ${isSelected ? 'is-active-output is-active-anchor' : ''} ${isBaseline ? 'is-baseline-msg' : ''}`}
                onClick={() => onSelectMessage?.(msg)}
                role="article"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectMessage?.(msg);
                  }
                }}
                aria-label={`Iteration ${index}: ${msg.prompt || 'Baseline'}`}
              >
                {/* Header Tag / Role */}
                <div className="msg-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                    <span className={`msg-role-tag ${isBaseline ? 'baseline-tag' : 'refine-tag'}`}>
                      {isBaseline
                        ? 'Anchor Baseline'
                        : msg.is_inpaint
                        ? 'Inpaint Edit'
                        : msg.is_wardrobe
                        ? 'Wardrobe Swap'
                        : `Iteration ${index}`}
                    </span>

                    {hasBgRef && (
                      <Badge variant="success" size="xs" icon={<Layers size={10} />}>
                        BG Harmonized
                      </Badge>
                    )}
                  </div>

                  <div className="msg-meta-row">
                    <span className="msg-seed-info">Seed: {msg.seed}</span>
                    {isSelected && (
                      <span className="active-badge active-anchor-pill">
                        <CheckCircle2 size={12} />
                        Active Anchor
                      </span>
                    )}
                  </div>
                </div>

                {/* Prompt Bubble */}
                <div className="msg-prompt-content">
                  {isBaseline ? (
                    <div className="baseline-prompt-text">
                      <span className="prompt-label">Baseline Prompt:</span>
                      <p>{msg.prompt || 'Synthesized initial creative baseline'}</p>
                    </div>
                  ) : (
                    <div className="user-prompt-text">
                      <span className="prompt-label">Refinement:</span>
                      <p>{msg.prompt}</p>
                    </div>
                  )}
                </div>

                {/* Visual Thumbnails: Output + Optional Background Reference */}
                <div className="msg-thumbnails-row">
                  {msg.image_url && (
                    <div className="msg-thumbnail-container">
                      <img
                        src={msg.image_url}
                        alt={`Output ${index}`}
                        className="msg-thumb-image"
                        loading="lazy"
                      />
                      <div className="thumb-overlay-hint">
                        <span>Master Viewport</span>
                      </div>
                    </div>
                  )}

                  {msg.background_reference_url && (
                    <div className="msg-thumbnail-container msg-bg-ref-thumb" title="Reference Background Used">
                      <img
                        src={msg.background_reference_url}
                        alt="Reference Background"
                        className="msg-thumb-image"
                        loading="lazy"
                      />
                      <div className="thumb-overlay-hint">
                        <span>Background Ref</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Loading Spinner in Chat */}
        {isGenerating && (
          <div className="refinement-generating-indicator" role="status" aria-live="polite">
            <div className="generating-spinner" />
            <div className="generating-text">
              <strong>Applying refinement...</strong>
              <span>
                {bg.activeBackground
                  ? 'Synthesizing scene with background perspective harmonization'
                  : 'Synthesizing changes conditioned on active output'}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box & Background Reference Controls */}
      <form className="refinement-input-form" onSubmit={handleSubmit} role="form" aria-label="Refinement Prompt Form">
        {/* Attached Background Reference Banner */}
        {bg.activeBackground && (
          <div className={`bg-attached-preview-card ${bg.isStagingConfigured ? 'has-active-staging' : ''}`}>
            <div className="bg-attached-left">
              <img
                src={bg.activeBackground.thumbnail_url || bg.activeBackground.image_url}
                alt="Attached Background Reference"
                className="bg-attached-thumb"
              />
              <div className="bg-attached-info">
                <div className="bg-attached-header">
                  <Badge variant="success" size="xs" icon={<Layers size={10} />}>
                    Background Attached
                  </Badge>
                  <span className="bg-attached-filename" title={bg.activeBackground.original_filename}>
                    {bg.activeBackground.original_filename || 'reference_bg.png'}
                  </span>
                </div>
                <span className="bg-attached-hint">
                  {bg.isStagingConfigured
                    ? `3D Staged: ${bg.spatialStaging.focal_length_mm}mm • ${bg.spatialStaging.camera_angle.replace(/_/g, ' ')} • ${bg.depthOfField.replace(/_/g, ' ')}`
                    : 'Perspective, depth of field & lighting harmonized via 3D Stage'}
                </span>
              </div>
            </div>

            <div className="bg-attached-actions">
              {/* Highlighted 3D Scene Stager Button */}
              <button
                type="button"
                className={`bg-stage-launch-btn ${bg.isStagingConfigured ? 'is-highlighted' : ''}`}
                onClick={() => bg.setIsStagerModalOpen(true)}
                title="Open 3D Spatial Scene & Camera Stager Studio"
                aria-label="Open 3D Spatial Scene Studio"
              >
                <Compass size={13} className={bg.isStagingConfigured ? 'text-cyan-400' : 'text-emerald-400'} />
                <span>{bg.isStagingConfigured ? '3D Scene Staged ✓' : 'Stage 3D Scene'}</span>
              </button>

              <button
                type="button"
                className="bg-attached-remove-btn"
                onClick={bg.handleRemoveActiveBackground}
                title="Remove attached background reference"
                aria-label="Remove background reference"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Textarea & Send Button Controls */}
        <div className="refinement-input-wrapper">
          <textarea
            ref={textareaRef}
            rows={2}
            className="refinement-textarea"
            placeholder={
              bg.activeBackground
                ? "Direct the harmonized scene (e.g. 'boys in front of window, camera facing window, zoom out slightly')..."
                : "Describe your refinements (e.g. 'Warm sunset golden hour lighting, softer depth of field')..."
            }
            value={promptInput}
            onChange={(e) => setPromptInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
            aria-label="Refinement Prompt Description"
          />

          <div className="refinement-input-footer">
            <span className="keyboard-hint">Cmd/Ctrl + Enter to send</span>
            <button
              type="submit"
              className="btn-primary btn-sm refine-send-btn"
              disabled={!promptInput.trim() || isGenerating}
            >
              {isGenerating ? (
                <span>Generating...</span>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>{bg.activeBackground ? 'Harmonize & Refine' : 'Refine Output'}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Background Reference Library Modal */}
      <BackgroundLibraryModal
        isOpen={bg.isLibraryOpen}
        onClose={() => bg.setIsLibraryOpen(false)}
        library={bg.backgroundLibrary}
        activeBackground={bg.activeBackground}
        onSelectBackground={bg.handleSelectBackground}
        onUploadBackground={bg.handleUploadBackground}
        onDeleteBackground={bg.handleDeleteBackground}
        isUploading={bg.isUploading}
        isLoading={bg.isLoadingLibrary}
      />

      {/* 3D Camera & Subject Spatial Stager Popup Modal */}
      {bg.activeBackground && (
        <CameraSpatialStagerModal
          isOpen={bg.isStagerModalOpen}
          onClose={() => bg.setIsStagerModalOpen(false)}
          backgroundImageUrl={bg.activeBackground.thumbnail_url || bg.activeBackground.image_url}
          stagingParams={bg.spatialStaging}
          onChange={bg.updateSpatialStaging}
          depthOfField={bg.depthOfField}
          onDepthOfFieldChange={bg.setDepthOfField}
          lightingMode={bg.lightingMode}
          onLightingModeChange={bg.setLightingMode}
        />
      )}
    </div>
  );
}
