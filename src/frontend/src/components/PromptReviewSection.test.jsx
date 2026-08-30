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

  it('calls onResyncPromptFromLevers when Re-sync Master Prompt from Levers button is clicked', () => {
    const onResyncPrompt = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPromptFromLevers={onResyncPrompt}
        onGenerateBaselines={vi.fn()}
      />
    );

    const resyncBtn = screen.getByRole('button', { name: /Re-sync Master Prompt from Levers/i });
    fireEvent.click(resyncBtn);
    expect(onResyncPrompt).toHaveBeenCalled();
  });

  it('calls onResyncLeversFromPrompt when Re-sync Levers from Prompt button is clicked', () => {
    const onResyncLevers = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncLeversFromPrompt={onResyncLevers}
        onGenerateBaselines={vi.fn()}
      />
    );

    const resyncBtn = screen.getByRole('button', { name: /Re-sync Levers from Prompt/i });
    fireEvent.click(resyncBtn);
    expect(onResyncLevers).toHaveBeenCalled();
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
        temperature={1.25}
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
    expect(screen.getByText(/3840x2160 \(16:9\) • Temp 1.25/i)).toBeInTheDocument();
  });

  it('renders temperature slider and invokes onTemperatureChange', () => {
    const onTempChange = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        temperature={1.0}
        onTemperatureChange={onTempChange}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    const slider = screen.getByLabelText(/Seed generation temperature/i);
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveValue('1');

    fireEvent.change(slider, { target: { value: '1.45' } });
    expect(onTempChange).toHaveBeenCalledWith(1.45);
  });

  it('renders conflict warning box when prompt conflicts exist', () => {
    const mockConflicts = [
      {
        id: 'c1',
        severity: 'warning',
        conflicting_elements: ['harsh afternoon sunlight', 'soft diffuse studio strobe'],
        categories: ['lighting'],
        explanation: 'Direct sun creates hard shadows which contradicts diffuse studio lighting.',
        recommendation: 'Choose either natural sunlight or controlled studio lighting.',
      },
    ];

    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        conflicts={mockConflicts}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    expect(screen.getByText(/Contradictory Visual Directives Detected \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText('harsh afternoon sunlight')).toBeInTheDocument();
    expect(screen.getByText('soft diffuse studio strobe')).toBeInTheDocument();
    expect(screen.getByText(/Direct sun creates hard shadows which contradicts diffuse studio lighting\./i)).toBeInTheDocument();
    expect(screen.getByText(/Choose either natural sunlight or controlled studio lighting\./i)).toBeInTheDocument();
  });

  it('invokes onCheckConflicts when Scan for Conflicts button is clicked', () => {
    const onCheckConflicts = vi.fn();
    render(
      <PromptReviewSection
        tagState={mockTagState}
        masterPrompt={mockTagState.master_prompt}
        narrative={mockTagState.narrative}
        onCheckConflicts={onCheckConflicts}
        onUpdateTagState={vi.fn()}
        onMasterPromptChange={vi.fn()}
        onNarrativeChange={vi.fn()}
        onResyncPrompt={vi.fn()}
        onGenerateBaselines={vi.fn()}
      />
    );

    const scanBtn = screen.getByRole('button', { name: /Scan for Conflicts/i });
    expect(scanBtn).toBeInTheDocument();
    fireEvent.click(scanBtn);
    expect(onCheckConflicts).toHaveBeenCalled();
  });
});

