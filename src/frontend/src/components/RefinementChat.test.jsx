import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RefinementChat from './RefinementChat';

describe('RefinementChat Component', () => {
  const sampleMessages = [
    {
      role: 'baseline',
      prompt: 'A cinematic high fashion model in studio lighting',
      generation_id: 'gen_base_01',
      image_url: 'https://example.com/base.png',
      seed: 4289102,
    },
    {
      role: 'user',
      prompt: 'Change lighting to warm golden hour',
      generation_id: 'gen_iter_01',
      image_url: 'https://example.com/iter1.png',
      seed: 4289102,
    },
  ];

  it('renders Active Anchor Banner and message timeline with active anchor indicator', () => {
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        activeGenerationId="gen_iter_01"
        activeSeed={4289102}
        onSendRefinement={vi.fn()}
      />
    );

    // Active Anchor Banner
    expect(screen.getByText('Active Refinement Anchor')).toBeInTheDocument();
    expect(screen.getByText('Seed #4289102')).toBeInTheDocument();
    expect(screen.getByText('Next prompt will refine from this image')).toBeInTheDocument();

    // Message list items
    expect(screen.getAllByText('Anchor Baseline').length).toBeGreaterThan(0);
    expect(screen.getByText('Iteration 1')).toBeInTheDocument();
    expect(screen.getByText('Active Anchor')).toBeInTheDocument();
  });

  it('calls onSelectMessage when clicking a past message card', () => {
    const handleSelect = vi.fn();
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        activeGenerationId="gen_iter_01"
        onSelectMessage={handleSelect}
      />
    );

    const baselineCard = screen.getAllByText('Anchor Baseline')[0];
    fireEvent.click(baselineCard);

    expect(handleSelect).toHaveBeenCalledWith(sampleMessages[0]);
  });

  it('calls onSendRefinement with typed prompt', () => {
    const handleSend = vi.fn();
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        onSendRefinement={handleSend}
      />
    );

    const textarea = screen.getByPlaceholderText(/Describe your refinements/i);
    fireEvent.change(textarea, { target: { value: 'Add brown leather trench coat' } });

    const submitBtn = screen.getByRole('button', { name: /Refine Output/i });
    fireEvent.click(submitBtn);

    expect(handleSend).toHaveBeenCalledWith('Add brown leather trench coat');
  });

  it('toggles wardrobe studio when Wardrobe button is clicked', () => {
    const handleToggleWardrobe = vi.fn();
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        onToggleWardrobe={handleToggleWardrobe}
        assignmentCount={2}
      />
    );

    const wardrobeBtn = screen.getByRole('button', { name: /Wardrobe/i });
    fireEvent.click(wardrobeBtn);

    expect(handleToggleWardrobe).toHaveBeenCalled();
    expect(screen.getByText('2')).toBeInTheDocument();
  });
});
