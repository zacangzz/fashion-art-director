import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import BaselineSelector, { parseAspectRatio } from './BaselineSelector';

describe('BaselineSelector', () => {
  const mockBaselines = [
    { id: 'gen_1', seed: 111, image_url: '/api/images/gen_1.png', created_at: '2026-08-24T00:00:00Z', aspect_ratio: '9:16' },
    { id: 'gen_2', seed: 222, image_url: '/api/images/gen_2.png', created_at: '2026-08-24T00:00:00Z', aspect_ratio: '9:16' },
    { id: 'gen_3', seed: 333, image_url: '/api/images/gen_3.png', created_at: '2026-08-24T00:00:00Z', aspect_ratio: '9:16' },
    { id: 'gen_4', seed: 444, image_url: '/api/images/gen_4.png', created_at: '2026-08-24T00:00:00Z', aspect_ratio: '9:16' },
  ];

  it('correctly parses various aspect ratio strings with parseAspectRatio helper', () => {
    expect(parseAspectRatio('9:16')).toEqual({
      cssRatio: '9 / 16',
      ratioValue: 9 / 16,
      orientation: 'vertical',
      label: '9:16',
    });

    expect(parseAspectRatio('16:9')).toEqual({
      cssRatio: '16 / 9',
      ratioValue: 16 / 9,
      orientation: 'horizontal',
      label: '16:9',
    });

    expect(parseAspectRatio('1:1')).toEqual({
      cssRatio: '1 / 1',
      ratioValue: 1.0,
      orientation: 'square',
      label: '1:1',
    });

    expect(parseAspectRatio('1.8:1')).toEqual({
      cssRatio: '1.8 / 1',
      ratioValue: 1.8,
      orientation: 'horizontal',
      label: '1.8:1',
    });

    expect(parseAspectRatio('2:3')).toEqual({
      cssRatio: '2 / 3',
      ratioValue: 2 / 3,
      orientation: 'vertical',
      label: '2:3',
    });

    expect(parseAspectRatio(null)).toEqual({
      cssRatio: '1 / 1',
      ratioValue: 1.0,
      orientation: 'square',
      label: '1:1',
    });
  });

  it('renders all 4 baseline candidates with seed tags and dynamic aspect ratio badge', () => {
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" aspectRatio="9:16" />);
    expect(screen.getByText(/Select Foundation Baseline Candidate/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #111/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #222/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #333/i)).toBeInTheDocument();
    expect(screen.getByText(/Seed #444/i)).toBeInTheDocument();
    expect(screen.getByText(/9:16/i)).toBeInTheDocument();
  });

  it('triggers onSelectBaseline when candidate card is clicked', () => {
    const onSelect = vi.fn();
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" onSelectBaseline={onSelect} />);

    fireEvent.click(screen.getByText(/Seed #222/i));
    expect(onSelect).toHaveBeenCalledWith(mockBaselines[1]);
  });

  it('allows toggling between Fit and Fill modes, and between 4 Cols and 2x2 Grid', () => {
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" aspectRatio="9:16" />);

    const fitBtn = screen.getByRole('button', { name: /Fit \(Full\)/i });
    const fillBtn = screen.getByRole('button', { name: /Fill/i });
    const cols4Btn = screen.getByRole('button', { name: /4 Cols/i });
    const grid2x2Btn = screen.getByRole('button', { name: /2×2 Grid/i });

    expect(fitBtn).toHaveClass('active');
    fireEvent.click(fillBtn);
    expect(fillBtn).toHaveClass('active');

    expect(cols4Btn).toHaveClass('active');
    fireEvent.click(grid2x2Btn);
    expect(grid2x2Btn).toHaveClass('active');
  });

  it('opens and closes the uncropped zoom preview modal with Escape key or close button', () => {
    render(<BaselineSelector baselines={mockBaselines} selectedBaselineId="gen_1" />);

    const zoomButtons = screen.getAllByTitle(/Zoom Preview/i);
    fireEvent.click(zoomButtons[0]);

    expect(screen.getByText(/Candidate #1 • Seed #111/i)).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: /Close \(Esc\)/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByText(/Candidate #1 • Seed #111/i)).not.toBeInTheDocument();
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
