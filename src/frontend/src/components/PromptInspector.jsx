import React, { useState } from 'react';
import { FileText, Copy, Check } from 'lucide-react';
import { Card, Badge, Button } from './ui';

/**
 * PromptInspector component for Studio Observability & Pipeline Traces.
 * Composes shared atomic UI primitives (Card, Badge, Button) to inspect
 * prompt formulation, system instructions, and negative constraint directives.
 *
 * @param {Object} props
 * @param {Object} props.run - Current selected generation run
 * @param {Object} [props.activeStep] - Active lifecycle stage step (if clicked)
 * @param {Function} [props.onResetStep] - Callback to clear active step and view full run
 */
export default function PromptInspector({ run, activeStep, onResetStep }) {
  const [copiedKey, setCopiedKey] = useState(null);

  if (!run) return null;

  const copyToClipboard = async (text, key) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(String(text));
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    } catch (err) {
      console.warn('Clipboard write failed:', err);
    }
  };

  const stepEv = activeStep?.event;
  const activePrompt = activeStep
    ? (stepEv?.prompts?.prompt || stepEv?.prompts?.user_prompt || stepEv?.inputs?.prompt || stepEv?.extracted_master_prompt || stepEv?.prompt || run.prompt)
    : (run.prompt || run.master_prompt);

  const activeSysInst = activeStep
    ? (stepEv?.instruction || stepEv?.system_instruction || stepEv?.config?.system_instruction || stepEv?.prompts?.system_instruction || run.system_instruction)
    : run.system_instruction;

  const activeNegPrompt = activeStep
    ? (stepEv?.negative_prompt || stepEv?.config?.negative_prompt || stepEv?.prompts?.negative_prompt || run.negative_prompt)
    : run.negative_prompt;

  const activeNarrative = activeStep
    ? (stepEv?.extracted_narrative || stepEv?.narrative || run.narrative)
    : run.narrative;

  const allPromptsText = [
    activePrompt ? `PRIMARY PROMPT:\n${activePrompt}` : '',
    activeSysInst ? `SYSTEM INSTRUCTION:\n${activeSysInst}` : '',
    activeNegPrompt ? `NEGATIVE PROMPT:\n${activeNegPrompt}` : '',
    activeNarrative ? `SCENE NARRATIVE:\n${activeNarrative}` : '',
  ].filter(Boolean).join('\n\n---\n\n') || (run.prompt || '');

  const wordCount = activePrompt ? activePrompt.split(/\s+/).filter(Boolean).length : 0;
  const charCount = activePrompt ? activePrompt.length : 0;

  return (
    <Card
      variant="bordered"
      className="obs-panel-card"
      icon={<FileText size={18} style={{ color: '#a855f7' }} />}
      title="Prompt Formulation & System Instructions"
      badge={activeStep ? (
        <Badge variant="purple" size="xs">
          Inspecting: {activeStep.label}
        </Badge>
      ) : null}
      actions={(
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {activeStep && onResetStep && (
            <Button
              variant="outline"
              size="xs"
              onClick={onResetStep}
              title="View full pipeline aggregated prompt"
            >
              Reset to Full Run
            </Button>
          )}
          <Button
            variant="secondary"
            size="xs"
            icon={copiedKey === 'full_prompt' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
            onClick={() => copyToClipboard(allPromptsText, 'full_prompt')}
          >
            {copiedKey === 'full_prompt' ? 'Copied' : 'Copy All Directives'}
          </Button>
        </div>
      )}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.85rem' }}>
        {/* 1. Primary Synthesized / User Prompt */}
        <div className="obs-prompt-block">
          <div className="obs-prompt-label-row">
            <span className="obs-prompt-label">Primary Generation Prompt / Synthesized Master Directive</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {activePrompt && (
                <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {wordCount} words ({charCount} chars)
                </span>
              )}
              <Button
                variant="outline"
                size="xs"
                icon={copiedKey === 'primary_prompt' ? <Check size={10} color="#10b981" /> : <Copy size={10} />}
                onClick={() => copyToClipboard(activePrompt || '', 'primary_prompt')}
              >
                Copy
              </Button>
            </div>
          </div>
          <div className="obs-prompt-text">
            {activePrompt || 'No primary prompt recorded for this trace or event.'}
          </div>
        </div>

        {/* 2. System Instructions / Metaprompt Directives */}
        <div className="obs-prompt-block">
          <div className="obs-prompt-label-row">
            <span className="obs-prompt-label">System Instruction / Multimodal Metaprompt Directive</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {activeSysInst && (
                <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {activeSysInst.length} chars
                </span>
              )}
              {activeSysInst && (
                <Button
                  variant="outline"
                  size="xs"
                  icon={copiedKey === 'sys_inst' ? <Check size={10} color="#10b981" /> : <Copy size={10} />}
                  onClick={() => copyToClipboard(activeSysInst, 'sys_inst')}
                >
                  Copy
                </Button>
              )}
            </div>
          </div>
          <div className="obs-prompt-text" style={{ color: activeSysInst ? 'var(--text-secondary)' : 'var(--text-muted)', fontSize: '0.76rem' }}>
            {activeSysInst || 'Standard Gemini baseline directives applied (no custom system instruction override recorded for this trace).'}
          </div>
        </div>

        {/* 3. Negative Prompt & Quality Constraints */}
        {activeNegPrompt && (
          <div className="obs-prompt-block" style={{ background: '#FEF2F2', borderColor: '#FEE2E2' }}>
            <div className="obs-prompt-label-row">
              <span className="obs-prompt-label" style={{ color: '#991B1B' }}>Negative Prompt / Artifact Avoidance Directives</span>
              <Button
                variant="outline"
                size="xs"
                icon={copiedKey === 'neg_prompt' ? <Check size={10} color="#059669" /> : <Copy size={10} />}
                onClick={() => copyToClipboard(activeNegPrompt, 'neg_prompt')}
              >
                Copy
              </Button>
            </div>
            <div className="obs-prompt-text obs-negative-prompt" style={{ fontSize: '0.76rem' }}>
              {activeNegPrompt}
            </div>
          </div>
        )}

        {/* 4. Extracted Scene Narrative (if distinct from prompt) */}
        {activeNarrative && activeNarrative !== activePrompt && (
          <div className="obs-prompt-block">
            <div className="obs-prompt-label-row">
              <span className="obs-prompt-label">Extracted Scene Narrative & Creative Context</span>
              <Button
                variant="outline"
                size="xs"
                icon={copiedKey === 'narrative' ? <Check size={10} color="#10b981" /> : <Copy size={10} />}
                onClick={() => copyToClipboard(activeNarrative, 'narrative')}
              >
                Copy
              </Button>
            </div>
            <div className="obs-prompt-text" style={{ color: 'var(--text-primary)', fontSize: '0.78rem' }}>
              {activeNarrative}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
