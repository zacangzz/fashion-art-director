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
  ArrowRight,
  Shirt,
} from 'lucide-react';

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
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

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
    onSendRefinement(promptInput.trim());
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

  return (
    <div className="refinement-chat-container" role="region" aria-label="Iterative Refinement Chat">
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
          Direct changes naturally in plain English or use the Wardrobe Studio to swap outfits with reference images.
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
                    {isBase ? 'Anchor Baseline' : activeMsg.is_inpaint ? 'Active Inpaint Anchor' : activeMsg.is_wardrobe ? 'Active Wardrobe Anchor' : 'Active Refinement Anchor'}
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
              Type instructions below like <q>Change the jacket to brown leather</q> or <q>Add warm late-afternoon sunlight</q>.
            </p>
          </div>
        ) : (
          conversationMessages.map((msg, index) => {
            const isBaseline = msg.role === 'baseline' || index === 0;
            const isSelected = activeGenerationId ? activeGenerationId === msg.generation_id : index === conversationMessages.length - 1;

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
                  <span className={`msg-role-tag ${isBaseline ? 'baseline-tag' : 'refine-tag'}`}>
                    {isBaseline ? 'Anchor Baseline' : msg.is_inpaint ? 'Inpaint Edit' : msg.is_wardrobe ? 'Wardrobe Swap' : `Iteration ${index}`}
                  </span>
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

                {/* Output Thumbnail Preview */}
                {msg.image_url && (
                  <div className="msg-thumbnail-container">
                    <img
                      src={msg.image_url}
                      alt={`Output ${index}`}
                      className="msg-thumb-image"
                      loading="lazy"
                    />
                    <div className="thumb-overlay-hint">
                      <span>Click to view in master viewport</span>
                    </div>
                  </div>
                )}
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
              <span>Synthesizing changes conditioned on active output</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form className="refinement-input-form" onSubmit={handleSubmit} role="form" aria-label="Refinement Prompt Form">
        <div className="refinement-input-wrapper">
          <textarea
            ref={textareaRef}
            rows={2}
            className="refinement-textarea"
            placeholder="Describe your refinements (e.g. 'Warm sunset golden hour lighting, softer depth of field')..."
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
                  <span>Refine Output</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
