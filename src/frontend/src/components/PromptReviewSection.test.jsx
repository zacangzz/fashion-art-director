import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PromptReviewSection from './PromptReviewSection';

describe('PromptReviewSection', () => {
  const mockTagState = {
    narrative: 'A sunlit editorial scene in a modernist pavilion.',
    master_prompt: 'High fashion editorial photo with warm golden light.',
    categories: {
      subject_details: [{ id: 's1', label: 'striking model', weight: 1.0, enabled: true, locked: false }],
      wardrobe_hair: [{ id: 'w1', label: 'charcoal blazer', weight: 1.2, enabled: true, locked: false }],
      lighting: [{ id: 'l1', label: 'warm direct sunlight', weight: 1.0, enabled: true, locked: false }],
    },
  };

  it('renders narrative input, master prompt textarea, and category levers', () => {
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    expect(screen.getByText(/Director's Master Prompt & Visual Levers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Scene Narrative & Core Logline/i)).toHaveValue('A sunlit editorial scene in a modernist pavilion.');
    expect(screen.getByLabelText(/Vision Director Master Prompt/i)).toHaveValue('High fashion editorial photo with warm golden light.');
    expect(screen.getByText('striking model')).toBeInTheDocument();
    expect(screen.getByText('charcoal blazer')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate 4 Baseline Candidates/i })).toBeInTheDocument();
  });

  it('calls onMasterPromptChange when prompt textarea is edited', () => {
    const onPromptChange = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={onPromptChange}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    const textarea = screen.getByLabelText(/Vision Director Master Prompt/i);
    fireEvent.change(textarea, { target: { value: 'Custom updated prompt' } });
    expect(onPromptChange).toHaveBeenCalledWith('Custom updated prompt');
  });

  it('calls onResyncPrompt when Re-sync Master Prompt button is clicked', () => {
    const onResync = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={onResync}
        onGenerateBaselines={vi.fn()}
      />
    );

    const resyncBtn = screen.getByRole('button', { name: /Re-sync Master Prompt/i });
    fireEvent.click(resyncBtn);
    expect(onResync).toHaveBeenCalled();
  });

  it('calls onGenerateBaselines when generate button is clicked', () => {
    const onGenerate = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={onGenerate}
      />
    );

    const generateBtn = screen.getByRole('button', { name: /Generate 4 Baseline Candidates/i });
    fireEvent.click(generateBtn);
    expect(onGenerate).toHaveBeenCalled();
  });

  it('displays Re-generate button label when hasBaselines is true', () => {
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
        hasBaselines={true}
      />
    );

    expect(screen.getByRole('button', { name: /Re-generate 4 Baselines/i })).toBeInTheDocument();
  });

  it('renders full prompt submitted to API preview panel with target resolution', () => {
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt="High fashion editorial photo with warm golden light."
        narrative={mockTagState.narrative}
        aspectRatio="16:9"
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Full Prompt Submitted to API \(Baseline Generation Preview\)/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/3840x2160 \(16:9\)/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Resolution: 3840x2160 \(Aspect ratio: 16:9\)\. 600 DPI ultra-high-resolution print quality\./i)
    ).toBeInTheDocument();
  });
});
