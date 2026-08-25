import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import BaselineSelector from './BaselineSelector';

describe('BaselineSelector', () => {
  const mockBaselines = [
    { id: 'gen_1', seed: 111, image_url: '/api/images/gen_1.png', created_at: '2026-08-24T00:00:00Z' },
    { id: 'gen_2', seed: 222, image_url: '/api/images/gen_2.png', created_at: '2026-08-24T00:00:00Z' },
    { id: 'gen_3', seed: 333, image_url: '/api/images/gen_3.png', created_at: '2026-08-24T00:00:00Z' },
    { id: 'gen_4', seed: 444, image_url: '/api/images/gen_4.png', created_at: '2026-08-24T00:00:00Z' },
  ];

  it('renders all 4 baseline candidates with seed tags', () => {
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" />);
    expect(screen.getByText(/Select Foundation Baseline Candidate/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #111/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #222/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #333/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #444/i)).toBeInTheDocument();
  });

  it('triggers onSelectBaseline when candidate card is clicked', () => {
    const onSelect = vi.fn();
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" onSelectBaseline={onSelect} />);

    fireEvent.click(screen.getByText(/Seed #222/i));
    expect(onSelect).toHaveBeenCalledWith(mockBaselines[1]);
  });

  it('renders prompt submitted to API panel and supports copying', async () => {
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: mockWriteText },
    });

    const baselinesWithPrompt = [
      {
        id: 'gen_1',
        seed: 111,
        image_url: '/api/images/gen_1.png',
        created_at: '2026-08-24T00:00:00Z',
        compiled_prompt: 'A sunlit architectural terrace with terracotta elements.',
      },
    ];

    render(<BaselineSelector baselines={baselinesWithPrompt} selectedBaselineId="gen_1" />);
    expect(screen.getByText(/Full Prompt Submitted to API \(Candidate Foundation\)/i)).toBeInTheDocument();
    expect(screen.getByText(/A sunlit architectural terrace with terracotta elements\./i)).toBeInTheDocument();

    const copyBtn = screen.getByRole('button', { name: /Copy Prompt/i });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    expect(mockWriteText).toHaveBeenCalledWith('A sunlit architectural terrace with terracotta elements.');
  });
});
