import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RefinementChat from './RefinementChat';

describe('RefinementChat Component', () => {
  const sampleMessages = [
    {
      generation_id: 'gen_root_001',
      prompt: 'Initial fashion editorial photography',
      created_at: '2026-09-01T10:00:00Z',
      image_url: 'https://example.com/root.png',
      cost_usd: 0.05,
      tokens: 1000,
    },
    {
      generation_id: 'gen_child_002',
      prompt: 'Make lighting warmer',
      created_at: '2026-09-01T10:05:00Z',
      image_url: 'https://example.com/child.png',
      cost_usd: 0.05,
      tokens: 1000,
    },
  ];

  it('renders chat message history with generation turns', () => {
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        activeGenerationId="gen_child_002"
        onSendRefinement={vi.fn()}
      />
    );

    expect(screen.getByText('Refinement Thread')).toBeInTheDocument();
    expect(screen.getByText('Initial fashion editorial photography')).toBeInTheDocument();
    expect(screen.getByText('Make lighting warmer')).toBeInTheDocument();
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

    expect(handleSend).toHaveBeenCalledWith('Add brown leather trench coat', expect.anything());
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

    const wardrobeBtns = screen.getAllByRole('button', { name: /Wardrobe/i });
    fireEvent.click(wardrobeBtns[0]);

    expect(handleToggleWardrobe).toHaveBeenCalled();
    expect(screen.getAllByText('2').length).toBeGreaterThan(0);
  });

  it('renders background reference button and opens library modal', () => {
    render(
      <RefinementChat
        conversationMessages={sampleMessages}
        onSendRefinement={vi.fn()}
      />
    );

    const bgBtns = screen.getAllByRole('button', { name: /Reference Background Library/i });
    expect(bgBtns.length).toBeGreaterThan(0);
    fireEvent.click(bgBtns[0]);

    expect(screen.getByText('Reference Background Library')).toBeInTheDocument();
  });
});
